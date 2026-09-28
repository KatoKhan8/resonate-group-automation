# TEN-ACCOUNT CANDIDATE SELECTION — 2026-09-28

**READ-ONLY SELECTION. THE TEN-ACCOUNT RUN IS NO-GO.**

Operator instruction, Zvonimir, 2026-09-28, narrowed mid-task: the run is
**refused for now**, it is not pending approval, and the instruction is to
**change the system to meet the `TASK-425` criteria — never to relax a
criterion to reach a number.** This document is the read-only candidate
selection and its evidence, and nothing in it is a launch plan.

    PROVIDER WRITES   0
    PROVIDER READS    0        (none were needed; see §7 for what that costs)
    STORE WRITES      0        production byte-identical, proved in §8

## 0. THE ANSWER, IN ONE LINE

**Zero accounts qualify under the frozen criteria, and the blocker is
structural rather than a shortage of accounts.** The estate holds 36 accounts
that are ICP-qualified, carry usable research and have a reachable decision
maker — but **not one is licensed for the 2–3 decision makers the criteria
require**, because every qualified account in the estate is ICP **tier C**, and
tier C licenses exactly **one**.

The honest number is therefore:

    accounts meeting the frozen criteria (2-3 decision makers)      0
    accounts meeting every criterion EXCEPT the decision-maker count 36
    of those, whose one contact classifies to a persona              33

Ten was never reachable by choosing better accounts. It is reachable only by
changing what the system knows about accounts — which is the instruction.

---

## 1. EVIDENCE STANDARD AND SHA-SIGNED INPUTS

Every claim below carries CLAIM / AUTHORITY / MEASURED AT / STATE. A test count
is never a PASS. An unreadable authority is UNKNOWN, and UNKNOWN never becomes
PASS, zero, absent, complete, safe or ready.

    CLAIM        the branch this work sits on
    AUTHORITY    git rev-parse
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — branch `task-ten-account-prep`, forked from
                 origin/master `4b1fb0c6`

    CLAIM        the store every number below was measured from
    AUTHORITY    sha256 of a read-only COPY of work/queue.jsonl
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — 1,582 records, all client `productive`
                 sha256 dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
                 campaigns.jsonl
                 sha256 ca7189676232c772a5f5d44a520ed154b5fcecfd09eaa944097b404b73dea370

    CLAIM        the freeze stands
    AUTHORITY    killswitch.workspace_state('productive')
    MEASURED AT  2026-09-28, this session, on BOTH the production
                 workspaces.jsonl and the snapshot
    STATE        VERIFIED — {'sending': False,
                 'why': 'sending.live is off for productive'}

**Why a copy.** `work/queue.jsonl` is read-only for this task, and a worktree
has no `work/` of its own — a probe run here resolves unbound. Every state
override in `store.STATE_OVERRIDES` is pointed at the snapshot, read from that
tuple rather than retyped, so a module added to the system cannot keep pointing
at the real directory while everything else moves. `scripts/ten_account_prep.py`
requires `--queue` and has no default, so it cannot silently open production,
and it installs a provider transport that raises — a provider call from it is a
defect that fails loudly, not a risk to be managed.

---

## 2. THE LADDER — every count named by the authority that answered it

Reproduce with:

    py -3 scripts/ten_account_prep.py --queue <snapshot>/queue.jsonl

```
  1582  total_records              store.load
   125  usable_research            research.for_prompt
    64  icp_qualified              qualify.state_of == qualified
     0  licensed_2_plus_dms        persona_plan.max_contacts_to_enrich >= 2
    20  has_2_stored_contacts      len(rec['contacts']) >= 2
     1  has_2_emailable            channels.email_verdict
     0  has_2_distinct_personas    personas.classify
```

**The 125 is not an estimate and not my definition.** It is the figure
`docs/FINDING-THE-RESEARCH-PACK-HAS-ONE-SHAPE-2026-09-28.md` §3 records —
"`research.for_prompt` and `generate.research_block` deliver on the same 125" —
and it reproduced exactly, from the production store, on the first run. Of
1,582 records, 394 carry a populated `research` list; the other 269 of those
carry only `weak`/`unusable` rows and correctly deliver nothing. **The
projection narrows and never widens**, so 125 is a ceiling on any selection that
needs research to license a claim.

### Where the ten accounts actually die

The gate is not contact data. It is the **ICP tier**.

    CLAIM        no account in the estate is licensed for 2-3 decision makers
    AUTHORITY    qualification.persona_plan.max_contacts_to_enrich, written by
                 routing.plan from routing.DEFAULT_CAPS
    MEASURED AT  2026-09-28, this session, over all 64 qualified records
    STATE        VERIFIED — 64 of 64 carry cap 1. Zero carry 2 or 3.

`routing.DEFAULT_CAPS = {'A': 3, 'B': 2, 'C': 1, 'REVIEW': 0, 'NOT_ICP': 0}`.
So "2–3 decision makers" is a property the **tier** grants, and:

    ICP tier over the 64 qualified-with-research      tier C -> 64
    ICP confidence over the same 64                   low -> 52, medium -> 12
    structural verdict over the reachable 36          icp_pass_with_uncertainty -> 36
    the tracks_time criterion over the same 36        unknown -> 36

Every qualified account is tier C. Every one of the reachable 36 passes as
`icp_pass_with_uncertainty` rather than `icp_pass`, and **on all 36 the
`tracks_time` criterion is `unknown`** while `productive.yaml` sets
`tracks_time_required: true`. The pass survives only because
`icpstructural.verdict_of` returns `ICP_PASS_WITH_UNCERTAINTY` when both
*defining* criteria (geography, company_type) pass — which is the correct
fail-soft, but it means **no account in this estate has ever been proved to
track time**, the single fact the entire offer rests on.

This is the same caveat `TASK-430` recorded from the other direction — "all 633
passes are tier C, `confidence: low`, `evidence_count: 0`" — and it is why "95%
pass" is not the reassurance it looks like.

### The second gate, and it is not the tier

    CLAIM        the estate has almost no reachable second contact
    AUTHORITY    channels.email_verdict, real productive config
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

Across the 20 qualified accounts that hold 2+ stored contacts there are 153
stored contacts and **16 are email-contactable**:

    verification_not_sendable   101
    no_email_address             21
    OK                           16
    mx_protection:barracuda      15

Exactly **one** account (`nineyards.ie`) has two contactable contacts, and
`personas.classify` puts **both on `champion`** — one persona, so no buying
committee, and nothing for criterion 1C's economic-buyer→operations swap to
move between. No account has three.

So even if the tier cap were lifted tomorrow, the contact data would still not
support a 2–3 person committee at more than one account. **These are two
independent shortages and they need two different fixes** — verification and
sourcing for the contacts, evidence depth for the tier.

---

## 3. THE COHORT — 36 accounts, one reachable decision maker each

**This is NOT a list of accounts that qualify.** Every row fails the frozen
decision-maker criterion. It is recorded because it is what the estate actually
holds, and because the operator's instruction is to change the system to meet
the criteria — which needs to start from the real shape of the data.

Per row: ICP verdict and its authority, the one contactable decision maker with
the persona `personas.classify` gives their real title, the count of
**ADMITTED** research facts that would license a prospect-facing claim, and the
approved offer that persona selects.

| domain | rec.state | icp_score | admitted facts | persona | offer | decision maker title |
|---|---|---|---|---|---|---|
| chicochamber.com | verified | 14.0 | 6 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Executive Officer |
| 2ton.com | verified | 41.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Operating Officer |
| azonetwork.com | verified | 47.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | CEO |
| waynemedia.com | verified | 41.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Operating Officer |
| hotsoupgroup.com | drafted | 46.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | CEO |
| savagebrands.com | verified | 39.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Founder and Chairman |
| yesandagency.com | verified | 47.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Financial Officer |
| thecommunity.ca | verified | 29.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Managing Director |
| advertisepurple.com | verified | 43.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Executive Officer |
| interest-media.com | verified | 33.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Co-Founder & CEO |
| invnt.com | verified | 56.0 | 5 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Financial Officer |
| e-2.at | drafted | 49.0 | 5 | champion | OFFER-B-OPERATIONS | Head Of Finance |
| grayloon.com | **held** | 47.0 | 5 | champion | OFFER-B-OPERATIONS | assoc design director |
| hypercrew.pl | verified | 17.0 | 5 | champion | OFFER-B-OPERATIONS | Head of Finance And Administration |
| 2020companies.com | verified | 4.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Financial Officer |
| anewagencyworld.com | verified | 41.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Managing Director |
| acqcom.com | approved | 7.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | COO & Co-Founder |
| brandiq.com | verified | 42.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Co-Chief Executive Officer |
| remerge.io | verified | 44.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Operating Officer & Co-Founder |
| chiefmedia.com | verified | 43.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Operating Officer |
| skyad.com | verified | 44.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Executive Vice President/COO |
| inmobi.com | verified | 48.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Vice President Corporate Strategy |
| eliassen.com | verified | 52.0 | 4 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Financial Officer |
| 5bonsai.com | verified | 0.0 | 3 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Executive Officer |
| studiopax.io | drafted | 7.0 | 3 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Founder |
| citycubes.be | verified | 13.0 | 3 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Founder & Creative Director |
| cgcreative.com | verified | 46.0 | 3 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Operating Officer |
| nineyards.ie | **held** | 53.0 | 2 | champion | OFFER-B-OPERATIONS | Head of Production |
| 1gslab.com | verified | 41.0 | 2 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Chief Executive Officer |
| 28row.com | verified | 47.0 | 2 | economic_buyer | OFFER-A-ECONOMIC-BUYER | COO / Co-Founder |
| adcuratio.com | verified | 15.0 | 2 | economic_buyer | OFFER-A-ECONOMIC-BUYER | COO |
| 4thwhale.com | verified | 39.0 | 1 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Executive Vice President (COO) |
| upperonestudiosinc.com | drafted | 0.0 | 1 | economic_buyer | OFFER-A-ECONOMIC-BUYER | Company Owner |
| 8ms.com | verified | 27.0 | 4 | **none** | **NONE** | Group Account Director |
| directmail.com | verified | 20.0 | 4 | **none** | **NONE** | Creative Director |
| wearejsa.com | **held** | 41.0 | 2 | **none** | **NONE** | Chief Creative Officer (CCO) |

Composition: `verified` 28 · `drafted` 4 · `held` 3 · `approved` 1.
Personas: `economic_buyer` 29 · `champion` 5 · **unclassified 3**.

**The last three rows carry no persona and therefore select no offer.**
`personas.classify` returns `(None, 0)` for "Group Account Director",
"Creative Director" and "Chief Creative Officer (CCO)" — none is in
`productive.yaml`'s champion or economic_buyer title lists. That is the correct
fail-closed answer (`personas.NOT_A_PERSONA`), not a bug to route around: a
contact with no persona has no angle, and `lint` raises
`domains_contact_no_angle`. They are listed so the gap is visible rather than
silently dropped.

**Three rows are `held`.** `held` is not a selection state and
`eligibility` has 13 distinct `held:` reasons. Their hold reason was not
resolved in this pass — **UNPROVEN**, and not to be read as available.

### The ICP verdict's authority, per account

Every row's verdict is the stored `qualification.verdict`, written by
`src/qualify.py:company -> src/icp.py:score` — deterministic code, no model.
The structural half is `icpstructural.structural`, configured from
`config/clients/productive.yaml` lines 85–142: five criteria (geography,
company_type, services_business, employees, tracks_time), `employees.min: 20`
with `tolerance: 0.30` giving an **effective floor of 14**. A representative
verdict, `savagebrands.com`:

    icp_status     qualified          icp_tier  C      confidence  low
    structural     icp_pass_with_uncertainty   eligible  True
    criteria       geography pass · company_type pass · services_business pass
                   employees pass · tracks_time UNKNOWN

### What licenses a prospect-facing claim, and what does not

    CLAIM        the claim licence for these accounts is admitted research only
    AUTHORITY    packfacts.pack_for -> pack["facts"], admitted by
                 packfacts.identity_of (ADMITTED / REFUSED / UNVERIFIABLE)
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — 1 to 6 admitted facts per account, 0 REFUSED and
                 0 UNVERIFIABLE across the cohort, and **2 CLIENT_SUPPLIED
                 facts on every one of the 36**

Every admitted fact in this cohort is a page read off the account's own site,
so `identity_of` admits it on the same-site test. **The two CLIENT_SUPPLIED
facts per account may not license a prospect-facing claim** — operator decision
7 and decision "B" of 2026-09-28: they stay available for qualification,
segmentation, prioritisation, strategy and offer selection, and where the only
evidence for a claim is one of those six fields the system **fails closed**.

Two live cautions on that, neither mine to fix and both already recorded:

- **`ISSUE-048` is open.** `packfacts` closes the `copylint`/`sequencegate`
  path only. `src/claims.py` is a second, independent claim gate whose support
  model is every `company_facts` key and value, so a client-CSV figure still
  licenses a claim there. Decision "B" is the temporary conservative policy;
  `TASK-462` is the replacement and is explicitly not to be built before
  `TASK-425`.
- **`ISSUE-055`** — `copylint._traces` licenses a short figure against any
  longer number containing it.

An account with one admitted fact (`4thwhale.com`, `upperonestudiosinc.com`)
can carry almost no personalised assertion. Four of the 36 sit at one or two
facts. **Admitted-fact count is the real depth measure here, not `icp_score`** —
note `5bonsai.com` and `upperonestudiosinc.com` at `icp_score: 0.0` and
`2020companies.com` at `4.0`, all still `qualified`, because under the
structural path the score is a priority inside the pool and not the gate.

### The offer each persona selects

    CLAIM        offer selection is persona-driven and only two offers are approved
    AUTHORITY    campaignstrategy._offers_for_segment, the only live importer
                 of offers.load()
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    offers.load()          8 offers
    approved               2   OFFER-A-ECONOMIC-BUYER · OFFER-B-OPERATIONS
    pending                6   OFFER-PM-001 · OFFER-TT-001 · OFFER-BU-001
                               OFFER-RP-001 · OFFER-BI-001 · OFFER-PR-001

    economic_buyer  ->  OFFER-A-ECONOMIC-BUYER  (profitability)
    champion        ->  OFFER-B-OPERATIONS      (project_management)

The two approved offers map 1:1 onto the client's two personas, so each persona
resolves exactly one offer and selection is unambiguous. Both carry
`campaigns: []`, so `offers.for_campaign()` would return nothing for any
campaign id — and it has no production caller anyway. The persona path is the
only one that resolves an offer, which is operator decision 5 (`TASK-427`)
working as decided.

Worth carrying forward: `config/clients/productive-offers.yaml` lines 50–57
declare `enforced_by: sequencegate checks step_objectives` and immediately
`enforcement_status: DATA_ONLY_NOT_YET_ENFORCED`. Confirmed — `sequencegate`
never reads `step_objectives`. The offer ladder is enforced at staging by
`bisonfactory`, not by that declaration.

---

## 4. EXCLUSION 1 — the TASK-430 companies, PROVED APPLIED

    CLAIM        all 32 companies TASK-430 recorded as failing the ICP gate
                 resolve to `rejected` through qualify.state_of in PRODUCTION
    AUTHORITY    qualify.state_of over a copy of the production queue
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — 32 of 32 resolve to `rejected`. None survived.

**Proved, not assumed — and the first thing the proof turned up is that "32
NOT_QUALIFIED" is two different numbers.** From
`work/TASK-430-icp-verdicts-2026-09-27.json`:

    bucket NOT_QUALIFIED        7    icp_status `rejected`, tier NOT_ICP
    bucket HOLD_UNKNOWN        25    icp_status `review`,   tier REVIEW
    blocked_by_sequencegate    32    = 7 + 25, and this is the gate figure

So 32 is "would not pass today's ICP gate", of which only 7 are rejected
outright and 25 are review. That distinction matters, because `state_of` maps
`review` to `review_required`, **not** to `rejected` — yet all 32 measure as
`rejected`. The reason is not the ICP verdict:

    CLAIM        what actually excludes the 32 is an operator human_review
    AUTHORITY    dmplan.human_review(rec)
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — 32 of 32 carry decision `reject`, by
                 "Zvonimir (operator) 2026-09-28", at 2026-09-28T10:38:17+00:00

    note: "NOT_QUALIFIED by operator decision 2026-09-28. TASK-430 ICP audit of
    campaigns 491-500; classifier src/qualify.py:company -> src/icp.py:score,
    deterministic, zero model cost. Recorded so this company can never be
    enrolled again. A verdict recorded today does not make any past send
    retroactively approved."

The chain is `qualify.state_of` line 51 — `human_review(rec).decision ==
REJECT -> REJECTED` — which fires **before** the `review -> review_required`
branch. So the exclusion holds through the operator's own ruling, and for 25 of
the 32 that ruling is the **only** thing holding it.

**Correction to the handoff, recorded because it was load-bearing.**
`docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md` §5 says "Verdicts were written
to a **copy**; production is byte-identical." That was true when written, and it
is **no longer the state**: production now carries the verdicts and the operator
rejections, stamped `2026-09-28T10:38:17+00:00`, while TASK-430's own file
records `prior_state: not_processed` for all 32. Production changed after that
audit ran. Anyone reading §5 today would conclude the exclusion is unenforced;
it is enforced.

### A SECOND, INDEPENDENT PROOF — the sequence gate

The exclusion does not rest on one reading. `sequencegate.check` refuses on the
qualification word itself, and `bisonfactory._plan` puts
`qualify.state_of(source)` on every lead, checked **per lead** by
`_refuse_sequence_gate`:

    qualified                PASSES
    dm_enrichment_approved   PASSES
    rejected                 REFUSED   "qualification is rejected: this sequence should not exist"
    review_required          REFUSED   "qualification is review_required: ..."
    not_processed            REFUSED   "qualification is not_processed: ..."
    classified               REFUSED   "qualification is classified: ..."

`sequencegate.BLOCKING_QUALIFICATIONS` is prefix-matched and contains
`REJECTED`, `REVIEW`, `NOT_PROCESSED` and `CLASSIFIED`. So the 32 are refused
twice, by two authorities, on two different fields.

**And a third, incidentally:** none of the 32 carries usable research —
`research.for_prompt` delivers on 0 of them — so they cannot enter the 125-record
pool at all. Three independent exclusions, none relying on the others.

### THE DEFECT: "can never be enrolled again" is fingerprint-bound

    CLAIM        the operator's reject is discarded when company facts change,
                 and 25 of the 32 then revert to review_required
    AUTHORITY    dmplan.human_review, which returns None when the review's
                 inputs_fingerprint != the qualification's inputs_fingerprint
    MEASURED AT  2026-09-28, this session, on in-memory copies; nothing written
    STATE        VERIFIED — negative control run on all 32

    before a fact refresh   rejected -> 32
    after a fact refresh    rejected ->  7      (the ICP verdict still rejects)
                            review_required -> 25

The 7 whose `icp_status` is itself `rejected` survive. **The 25 whose only
authority is the operator's ruling lose it**, because a stale review authorises
nothing — which is correct for a review that *permits*, and wrong for one that
*forbids*. The note says "recorded so this company can never be enrolled
again"; the mechanism cannot deliver that across a fact refresh. Recorded in
`PRODUCT-GAPS.md`. **Not fixed here — `src/` is out of scope for this task.**

The 25 at risk: agoc.com · brandbuildersgroup.com · danads.com ·
eatbreadless.com · edisonlitho.com · einsteinmedical.com ·
firstclasssolutions.com · fortressbrand.com · glocap.com · goloadup.com ·
logosyork.org · loyaltybrands.com · mail.roanoke.edu · metrostudio.com ·
mintlanguages.com · mocalogistics.com · modernb2b.co · oneworlduv.com ·
rightspend.com · schatzpublishing.com · scsglobalservices.com · speero.com ·
thecontentauthority.com · whycms.com · yellowtail.nl

---

## 5. EXCLUSION 2 — the ISSUE-054 old 3-step copy, PROVED ABSENT

    CLAIM        no selected account carries the OLD 3-STEP copy
    AUTHORITY    rec["cadence"] step keys, over the production copy
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — 0 of the 36, and 0 of the 20 with 2+ contacts

The old-copy population, measured rather than taken from the issue text:

    contact cadences with step keys exactly {em1, em2, em3}   1,272
    records holding at least one                              1,031
    qualify.state_of across them        not_processed 1,238 · rejected 34
    of them QUALIFIED                                             0

**Zero.** ISSUE-054's 256 are a subset of these 1,272 — the ones for which
`no_repetition/subjects` was the only failure — and the exclusion generalises
past them: **every record carrying old 3-step copy is `not_processed` or
`rejected`, never `qualified`.** This confirms the operator's measurement ("all
256 currently carry ICP `not_processed`") and strengthens it, because it covers
the whole 1,272 rather than the 256.

So a selection that requires `qualify.state_of == qualified` excludes the entire
old-copy population **structurally** — not by a list to remember, but because
the two conditions cannot hold at once on any record in this store. The same
`sequencegate` table in §4 is the second, independent refusal: `not_processed`
and `rejected` both refuse by name.

For the shape, the whole cadence distribution:

    ('em1','em2','em3')                                       1272   OLD
    ('em1'..'em5','li1'..'li6')                                 39   canonical
    ('li1'..'li6')                                              23
    everything else                                             19

---

## 6. WHY THE CRITERIA CANNOT BE MET TODAY — the four TASK-425 verdicts

This section exists because the operator's instruction is to change the system
to meet the criteria. It states where the criteria actually stand.

    CLAIM        TASK-425 did not pass, and it ran on a FIXTURE
    AUTHORITY    docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md on
                 origin/task-425-one-account-dry-run
    MEASURED AT  branch head 2d54e274, run at 2026-09-28T10:31:48Z
    STATE        VERIFIED from the artifact

    1 causal matrix      BLOCKED    on C and D, both NOT COMPARABLE
    2 signature chain    BLOCKED    `sender_signature` exists nowhere
    3 offer sequencing   PASSED     with its negative test
    4 audit artifact     PASSED     per message, provider writes 0

**The branch head moved.** The midday handoff names `88649410`; it is now
`2d54e274`, and the re-run **lost two criteria it had previously claimed**,
because the 08:33Z matrix compared three different people across its runs. The
handoff's own warning — "treat criteria 1 and 4 as strong evidence awaiting
confirmation" — resolved against criterion 1.

**The account was `Brightmoor Studio` — "a fixture, reserved domain, invented
people", with the production queue never opened.** So the frozen criteria have
never been exercised against a real production account, which is consistent with
§2: no real account is licensed for the 2–3 decision makers the fixture had.
The fixture had three invented people precisely because no real account has
three.

    CLAIM        criterion 2 cannot be met by any account selection
    AUTHORITY    grep for `sender_signature` across src/ and config/
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — zero occurrences in the entire codebase

Launch blocker 3 stands: no mailbox has a stored signature, 155 email steps
render empty. **No choice of accounts can fix this**, which is why it is listed
here rather than treated as a selection problem.

### Two more standing gates on any ten-account run

    CLAIM        decision 13's send-ledger precondition is unmet
    AUTHORITY    record events over the production copy
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — across 28,355 recorded events on 1,582 records
                 there is not one send event. Kinds present are
                 provider_call_planned / _skipped / _started / _completed,
                 draft_generated / _approved, lint_failed, and so on.
                 The action ledger holds 136 rows: attempted 64 · abandoned 41
                 · unresolved 26 · failed 5 — and no `sent`.

Decision 13 is explicit: **"SEND LEDGER IS P0, BEFORE ANY TEN-ACCOUNT RUN"**,
with behavioural acceptance (`already_sent` true on known really-sent contacts,
reconciled against the provider, the digest stops saying "no confirmed sends").
None of the three holds. This alone forbids the run independently of selection.

    CLAIM        decision 15 lists ten accounts under NOT NOW
    AUTHORITY    docs/OPERATING-MODE.md decisions 15 and 16
    MEASURED AT  2026-09-28, read this session
    STATE        VERIFIED — decision 15 refuses "ten accounts" until the
                 operator reopens it; decision 16 places it fourth, after
                 TASK-425's review, the send ledger, and the cross-channel
                 stop design.

---

## 7. WHAT THIS SELECTION DOES NOT KNOW — UNKNOWN, not clean

**Provider reads: 0.** Nothing here was checked against EmailBison or HeyReach,
because a read-only selection did not need one and the run is no-go. The
consequence must be stated rather than glossed:

    CLAIM        whether anyone at these 36 accounts is already in a sequence
    AUTHORITY    collision.check_account — NOT CALLED
    MEASURED AT  not measured
    STATE        **UNKNOWN**

`collision.account_policy` returns HOLD with "the provider estate could not be
read for this account, so nobody can say whether somebody there is already in a
sequence" precisely for this case, and `CollisionUnknown` exists so that "we
could not check" is never reported as CLEAR. Under ARCHITECTURAL INVARIANT 0
this stays UNKNOWN. **It is not zero, not clear and not safe.** For scale: on
**2026-09-18** a collision walk put 65 accounts in this estate at `stop`,
"somebody at this account is mid-sequence right now"
(`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md` line 40). **That
figure is ten days old and is not re-measured here** — it is cited only to say
that a non-trivial collision rate is the expectation rather than the exception,
and it is UNPROVEN as a statement about today.

Also unmeasured and therefore UNKNOWN: the hold reason on the three `held`
accounts; sender headroom for any of the 36; whether the 101
`verification_not_sendable` contacts would verify if re-run.

---

## 8. PRODUCTION WAS NOT TOUCHED

    CLAIM        no production state file changed
    AUTHORITY    sha256 before and after, from a FRESH process
    MEASURED AT  2026-09-28, this session, after every measurement above
    STATE        VERIFIED — byte-identical

    queue.jsonl      dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
    campaigns.jsonl  ca7189676232c772a5f5d44a520ed154b5fcecfd09eaa944097b404b73dea370

Content, not mtime — `mtime` is the wrong instrument here, as the TASK-425
findings §0g records, because ~15 loops write the main checkout's `work/` and
`queue.jsonl` changes inside any run window for unrelated reasons. No `src/`
file was modified. This branch adds two files: this document and
`scripts/ten_account_prep.py`, plus one appended section in `PRODUCT-GAPS.md`.

---

## 9. NOT APPROVED — FOR A RUN THAT IS NO-GO

**Everything in this section describes a run the operator has REFUSED.** It is
kept only because it is a measured finding about the dry-run path that the work
to "change the system to meet the criteria" will need. **It is not a plan, not a
checklist, and not a green light.** Nobody may read it as authorisation.

The operator's dry-run definition — *execute the real decision and safety path
without provider writes* — is **half true on master `4b1fb0c6`**, and the half
that is missing is the estate half.

    CLAIM        a dry run runs the copy gates and NOT the estate gates
    AUTHORITY    src/bisonfactory.stage source, by line
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED by reading the module and by executing its proof test

    _refuse_copylint          line 121   RUNS on a dry run
    _refuse_sequence_gate     line 153   RUNS on a dry run
    if not live: return       line 155-166
    bison.bound_workspace()   line 175   live only
    _ensure_leads             line 204   live only

Inside `_ensure_leads`, and therefore **never reached by a dry run**:
`_refuse_colliding_leads`, `killswitch.workspace_state`,
`_refuse_bad_greetings`, `_refuse_unsupported`, `_refuse_unvariabled_leads`,
`_refuse_blank_render`.

The collision gate is doubly unreachable: it is guarded by
`workspace_id = (report.get("workspace") or {}).get("id")`, and on a dry run
`report["workspace"]` is still `None`, so the guard is falsy even if the line
were reached.

So the fix recorded in OPERATING-MODE landed for criterion 3 and only for
criterion 3. `tests/test_a_dry_run_runs_the_sequence_gate.py` runs 8/8 here,
including a negative control and a test that the booby-trap itself fires —
**and a test count is not a PASS.** Ladder position: **INTEGRATION_TESTED**, not
LIVE_VALIDATED. Note also, from the artifact, that `generate.run` has no caller
in this repository but its own harness and `tests/`.

**The consequence, stated plainly:** a dry run proves the copy and the sequence,
and proves **nothing** about the estate. Any future zero-write rehearsal that
reports "all gates passed" would be reporting on two gates out of eight. That is
a system change to make before a ten-account run is discussable — not a
procedure to work around.

---

## 10. WHAT WOULD HAVE TO CHANGE, IN THE OPERATOR'S DIRECTION

Not a plan and not a dispatch — the honest list of what stands between the
estate and the frozen criteria, from the measurements above.

1. **Evidence depth, to move accounts off tier C.** Every qualified account is
   tier C at cap 1, and every reachable one passes as
   `icp_pass_with_uncertainty` with `tracks_time` UNKNOWN. Until an account can
   reach tier B, "2 decision makers" is not licensable for anybody.
2. **`sender_signature` must exist.** Criterion 2 is unmeetable while the field
   is absent from the codebase. It is an operator and client content decision,
   not an implementation one.
3. **The send ledger** — decision 13, P0, with its three behavioural
   acceptances. Independently blocking.
4. **Contact verification and sourcing.** 101 of 153 candidate contacts are
   `verification_not_sendable` and 21 have no address. One account in the estate
   has two reachable people.
5. **The estate gates must be reachable without provider writes**, or the
   collision and suppression state of a cohort stays UNKNOWN before a run
   rather than after it.
6. **The fingerprint-bound rejection** in §4 — 25 companies the operator ruled
   may never be enrolled again would silently become `review_required` on a
   fact refresh.

Items 1, 2, 3 and 5 are each independently sufficient to keep the run no-go.
