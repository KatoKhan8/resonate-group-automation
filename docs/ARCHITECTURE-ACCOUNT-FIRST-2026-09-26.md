# ACCOUNT IS THE UNIT — operator clarification, 2026-09-26

Two operator directives, given 2026-09-26 during the Phase 1 session, recorded
here as standing architectural requirements alongside
`docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md`.

**Neither directive authorises a new orchestration system, and neither is a
reason to pause, restart or reprioritise work in flight.** The operator said so
twice, explicitly. What follows is the requirement, then the measurement of
what already satisfies it.

---

## 1. THE REQUIREMENT

**The primary research and strategy unit is the ACCOUNT / COMPANY, not the
individual lead.** Target 2-3 relevant decision makers inside the same company,
across both Email and LinkedIn.

    ACCOUNT
    -> company research pack
    -> account qualification
    -> account hypothesis
    -> relevant campaign offer(s)
    -> buying committee / decision makers
    -> person-role relevance
    -> coordinated Email + LinkedIn outreach

Company research happens **once per account** and is reused; a lighter
person-level relevance layer sits on top of it. Role shapes interpretation and
angle, not the underlying evidence:

    CEO / Founder          business impact, growth, margin, visibility
    COO / Operations       delivery, resourcing, utilization, operational control
    Head of Delivery / PM  projects, capacity, budgets, workflow

Three contacts at one company are **not** three unrelated campaigns. A reply or
meaningful interaction from one decision maker must be able to affect strategy
for the others. A referral raises the referred contact's priority and carries
context. One person's "not interested" is **not** a company-wide DNC. A
company-level removal request suppresses the whole account.

Cross-reference between decision makers and channels is permitted **only when
evidence supports it.** Never fabricate an internal conversation or imply we
spoke to a colleague we did not speak to.

**LinkedIn stays heavy.** The existing cadence tree was directionally strong
and is not to be simplified because Phase 1 is being rebuilt. The thing to
improve is the COPY and its coordination with Email: Email carries the
structured commercial argument, LinkedIn carries lighter context, observations
and account-specific touches. LinkedIn must complement Email, not paraphrase
it. **Inspect and document the actual tree before modifying it.**

## 2. THE NEXT LAYER, DOCUMENTED AND NOT BUILT NOW

Account-level orchestration is the intended layer **after** the Second Brain,
Offer Engine, skills and copy architecture are stable:

    ACCOUNT -> BUYING COMMITTEE -> PRIMARY CONTACT -> EMAIL + LINKEDIN
    -> INTERACTION / NO INTERACTION -> NEXT BEST ACTION
    -> SAME CONTACT / SECOND CONTACT / THIRD CONTACT / PAUSE / STOP

Eventually the system decides who to contact first, primary vs secondary, which
channel first, when to introduce the second or third contact, when activity from
one contact changes outreach to another, when to increase, reduce, pause, or
stop the whole account.

**Do NOT build that decision engine now.** The Phase 1 obligation is narrower
and purely negative: **the data model and Second Brain must not block it.**
Preserve these relationships and avoid any decision that permanently models a
lead as an isolated campaign unit:

    ACCOUNT <-> CONTACTS <-> ROLES/PERSONAS <-> CAMPAIGN <-> OFFERS
    <-> ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE <-> EMAIL STATE
    <-> LINKEDIN STATE <-> INTERACTIONS <-> REPLIES <-> REFERRALS
    <-> SUPPRESSION <-> OUTCOMES

## 3. WHAT ALREADY SATISFIES THIS, MEASURED ON MASTER AT `e4dc021c`

**This is not a new architecture. The account is already the unit of outreach
here, in code and in documentation.** Per `OPERATOR-DIRECTIVES-2026-09-25.md`
§6 and the Phase 1 directives §1, the correct response is to wire and verify
what exists, not to build a second implementation of it.

    ACCOUNT-OUTREACH.md §4     the touch graph
    ACCOUNT-OUTREACH.md §8     referrals
    ACCOUNT-OUTREACH.md §10    reply effects, and "four things that never move"
    ACCOUNT-OUTREACH.md §11    decision-maker priority: primary, secondary,
                               tertiary, referral. Escalation conditions are
                               cadence branches `other_dm_replied` and
                               `referral_received`, not hidden rules
    ACCOUNT-OUTREACH.md §12    revival
    ACCOUNT-INTELLIGENCE.md    what is happening at an account, and why a
                               priority score is never permission to write
    CADENCE-MODEL.md           the cadence model

    src/account.py             contacts_of, touches, replies, bounces,
                               referrals, referred_by, referred_to, graph,
                               timeline, team_for, has_confirmed_touch
    src/accountpolicy.py       classify_outcome, resolve, affected(rec,
                               contact_key, outcome), effects, _hold_contact,
                               _stop_contact, _suppress_contact
    src/accountstate.py        UNTOUCHED SEQUENCED ENGAGED REPLIED MEETING WON
                               LOST DO_NOT_CONTACT
    src/accountsaturation.py   fatigue
    src/personas.py, roles.py  persona and role vocabulary
    src/revival.py             the gone-quiet question

The operator's specific rules are already implemented, not merely planned:

- *"one person says not interested is not a company-wide DNC"* is
  `ACCOUNT-OUTREACH.md` §10 **"Only a removal request suppresses"** — only
  `unsubscribe` and `account_do_not_contact` set `unsubscribed`.
- *"a referral makes the referred contact the priority with context"* is §8
  Referrals plus `account.referred_to` / `referred_by` and
  `accountpolicy.affected`.
- *"the replier stops being cold-sequenced"* is §10 **"The replier is never
  left to carry on."**
- *"nobody engages, introduce another decision maker per policy"* is §11's
  `other_dm_replied` cadence branch.
- *"uncertainty must not narrow"* is §10 **"Uncertainty never narrows"** — an
  unclassified outcome resolves to review at ACCOUNT scope.
- *"nothing subtracts"* — `apply_reply` writes only absent state, so no replay
  or reclassification can lift a hold or a suppression.

## 4. THEREFORE THE REAL GAP

The gap is **not** the account model. It is whether the Phase 1 copy path
consumes it.

`src/secondbrain.py` retrieves per `(task, client)` and has **zero callers**.
It has no account parameter at all, so as merged it cannot express "research
this company once and layer three contacts on top" — not because the account
model is missing, but because the retrieval layer was built without reference
to it and nothing calls it.

That is the same DISCONNECTED finding the Phase 1 directives §1 are about, and
it is measured by **TASK-324**, fixed for provenance by **TASK-322**, and wired
by **TASK-321**. The account-first requirement is therefore satisfied by
completing Phase 1 as planned, with one addition: `secondbrain` retrieval must
be account-scoped, with person relevance layered on it, so the cost of company
research is paid once per account rather than once per contact.

**Cost consequence, which is also the operator's argument for it:** the fifty
cost 10.15c per lead against a 0.3c target, and Sonnet is 96% of that. Company
research regenerated per contact instead of per account multiplies the dominant
cost by the number of decision makers. Account-scoped retrieval is the
structural version of the batching and caching levers.

## 5. WHAT IS FORBIDDEN BY THIS DOCUMENT

- Do not build the orchestration decision engine in Phase 1.
- Do not create a parallel account store, contact store, or second source of
  truth for a company fact. `productive.yaml` stays canonical for client facts
  and `work/queue.jsonl` via `src/store.py` stays canonical for record state.
- Do not simplify, shorten, or replace the LinkedIn cadence tree. Document it
  first; change it only under a separate, intentional review.
- Do not shorten the five-step email cadence or its threading.
- Do not fabricate a cross-reference between contacts.
- Nothing is sent and nothing is activated. The production freeze in
  `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` is unchanged.
