# Operator authorization - 2026-09-16

Granted by the operator during the overnight
autonomous run, in writing, in response to Claude's blocker report naming
exactly these two acts as the only things standing between approved inventory
and a first real send.

**Recorded here so they never have to be requested again after a context or
session reset.** A fresh session may act on this file without re-asking.

---

## 1. HeyReach - `heyreach.add_lead_to_list` is ENABLED

> "Approve enabling `heyreach.add_lead_to_list` for the controlled Productive
> production path. Proceed with the unbound-list staging approach you
> described. This approval is specifically for adding approved Productive
> leads to the unbound HeyReach list for staging."

**Scope:** adding APPROVED Productive leads to an UNBOUND HeyReach list, for
staging. Nothing else.

**Explicitly NOT granted:**

> "Do NOT interpret this as permission to bypass gates or activate arbitrary
> campaigns."

Every existing gate is preserved by instruction: tenancy, collision,
prior-contact and history, approval and fingerprint, fatigue, caps,
killswitch, provider readback, audit and ledger, and every fail-closed
default.

**What this does NOT change.** `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` stays
`False`, and `LINKEDIN_ADD_LEAD` stays resealed - it is refused on the first
line of its own condition. Adding a lead to a HeyReach CAMPAIGN activates that
campaign, in PAUSED and in FINISHED both, and that remains the prospect-facing
moment. This authorization is for the LIST route, whose safety property is
that the list is attached to no campaign, checked against the provider at the
moment of the write by `liststaging.assert_list_safe`.

**After staging is proven by provider readback**, the operator authorizes
proceeding "with the already-authorized controlled canary path and move toward
LIVE/SENDING".

---

## 2. EmailBison - the EMAIL CONTROL sequence is APPROVED (cohort is 11)

> "Approve the EMAIL CONTROL sequence for the recommended 10-contact
> Productive cohort. Proceed: CONTROL approval → campaign write → provider
> readback → controlled activation → LIVE/SENDING."

**Scope:** the CONTROL sequence - `persona_pain -> comparable_proof ->
breakup`, threading F/T/F - for the cohort Claude recommended: the contacts
that survive the collision check AND whose persona resolves, so the angle is
their own rather than the champion persona's finance default.

**The cohort is ELEVEN, not ten.** The grant says "10-contact" because that is
the number Claude reported when asking. It was wrong by one, in Claude's
arithmetic rather than in the operator's decision: 16 of 17 survive the
collision check, 5 of those 16 carry `persona=None`, so 16 - 5 = 11. The "10"
came from 16 - 6, which subtracted one contact twice - the contact the
collision check excluded was itself one of the six with `persona=None`. The SET
is exactly the one the operator described; only the count was mis-stated.
Resolved against live state and confirmed: 11 contacts, all `sendable: True`,
in state `verified` or `drafted`.

This is the operator's human read, which is what `operator-control-arm`
approval means and what `pushable` was retired in favour of. Approval steps
written under this authorization are attributed:

    <operator email> (operator authorisation 2026-09-16)

where `<operator email>` is the operator's own address as configured in
`git config user.email`, matching the precedent already in the estate from
2026-09-13. The address itself is not written here: the PII guard requires
every email address in a tracked file to be on a reserved domain, and it is
right to - a rule with an exception for the person who set it is not a rule.
The attribution is written into `work/queue.jsonl`, which is gitignored.

**Every other gate preserved by instruction:** verification, collision,
tenancy, approval, killswitch, fatigue, sender capacity and audit.

**Not granted:** approval for the other 5 of the 16 surviving contacts, the
590 unapproved steps elsewhere in the estate, or any bulk approval mechanism.
Approval remains per-step and per-contact.

---

## 3. Provider writes in this session

> "Also allow the required provider-write commands in this session when the
> auto-mode classifier asks for confirmation."

Claude's first attempt at the EmailBison campaign write was refused by Claude
Code's auto-mode classifier - a harness control, not a gate. The operator has
undertaken to confirm those prompts. Claude did not and must not work around
the classifier.

---

## 4. What is still NOT authorized

Recorded so the boundary stays visible as these two paths proceed.

    bison.add_lead        not in SUPPORTED. The Bison staging path reaches
                          leads through bisonfactory's own gates, not through
                          providerwrites.perform - see TASK-198 and
                          docs/OPERATOR-DECISION-2026-09-16.md.
    bison.activate        not in SUPPORTED. "Controlled activation" is
                          authorized as an OUTCOME above; the verb is not
                          wired, so reaching it is a separate step and the
                          operator is to be told what it requires.
    heyreach.activate     not in SUPPORTED.
    LINKEDIN_ADD_LEAD     in SUPPORTED and hard-sealed by
                          CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False.
    approval in bulk      forbidden. Named in the checkpoint as the most
                          damaging action available here.

> "Do not create additional approval gates around these already-approved
> decisions."

So: no new gate is to be invented in front of either path. The instruction
cuts both ways - the existing gates stand, and nothing new is added to slow
what has been approved.

---

## 5. The standing obligation after every real write

> "After each real provider write: READ BACK PROVIDER TRUTH → reconcile
> ledger → report actual state → continue."

A write with no readback is a write nobody can classify. This is already the
contract in `providerwrites.perform`, which takes a `readback` and treats a
missing one as a refusal; this authorization restates it as an operating
obligation rather than a code detail.


---

## 6. HeyReach - `heyreach.create_campaign` is ENABLED for list 940797

> "APPROVED - enable heyreach.create_campaign for list 940797"

**Scope:** creating a campaign bound to list **940797**, enforced by
`_list_is_ours_and_unbound_and_holds_approved`, which takes a LIST id because
the campaign does not exist yet at the moment of the write. It reads the list
live and refuses unless it is ours, in our tenant, unbound, and holding only
approved leads.

**Not prospect-facing, on the provider's own terms.** `create_campaign`
creates in DRAFT, and its docstring records that "A DRAFT SENDS NOTHING.
Activation is `/campaign/StartCampaign`". Maximum send exposure of this grant
is ZERO.

**What it costs, and it is one-way.** TASK-216 established that the bind is
`linkedInUserListId` supplied at creation - there is no separate attach route.
So the moment creation succeeds, list 940797 stops being unbound. That ends the
staging safety property the list has carried all day, and
`liststaging.assert_list_safe` will correctly refuse every later add to it. A
future cohort needs a different unbound list.

**Explicitly NOT granted:** `heyreach.activate` / `/campaign/StartCampaign`.
It is implemented (TASK-218) with `expect_leads` containment and provider-answer
classification, it is registered in `WRITE_ROUTES`, and it stays out of
`SUPPORTED`. A test asserts that. `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` remains
False and `LINKEDIN_ADD_LEAD` remains sealed - we never add to campaign 599020.

**Still owed before activation can be asked for:** `heyreach.activate` has no
`CONDITIONAL` entry, so enabling it as-is would be a channel-wide licence
rather than one scoped to the canary campaign. That entry must be written,
scoped to the campaign id this grant produces, before activation is requested.

---

## heyreach.create_list - EXERCISED 2026-09-16

Grant, verbatim: "APPROVED - enable heyreach.create_list"

Exercised once. `scripts/stage_linkedin_ready_cohort.py --live` created:

    list 943957   "RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16"
                  campaignIds []  - UNBOUND
                  4 leads, read back from the provider

The 4 are the full cohort that passes every existing gate: operator-control-arm
approval on li1-li5, a canonical profile URL, and an ACCOUNT whose
`collision.account_policy` verdict is neither hold nor stop. One account
(2 contacts) is HELD and was not staged. No gate was widened to reach 4.

`LINKEDIN_CREATE_LIST` was added to `SUPPORTED` with NO `CONDITIONAL`
predicate, deliberately: a create has no destination to check and an empty
list reaches nobody. What bounds this is downstream -
`LINKEDIN_ADD_LEAD_TO_LIST` requires an unbound list and
`LINKEDIN_CREATE_CAMPAIGN` requires a list that is ours, unbound and holding
only approved leads.

### SCOPE EXTENSION NOT YET GRANTED - do not assume it

The `heyreach.create_campaign` grant was worded "for list **940797**". List
940797 is now bound to campaign 604869 and holds only the HELD contact, so it
is a dead end. Binding a campaign to list **943957** is outside the wording of
that grant.

Likewise `heyreach.activate`'s condition is scoped to campaign **604869**, and
`bison.activate`'s to campaign **485** - both of which are being replaced.

These three re-scopings are operator decisions. They have NOT been granted and
must not be inferred from the earlier wording.
