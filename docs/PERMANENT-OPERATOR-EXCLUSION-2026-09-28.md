# THE PERMANENT OPERATOR EXCLUSION — 2026-09-28

**Operator decision "B", Zvonimir, 2026-09-28.** Branch
`task-permanent-operator-exclusion`. Off the critical path; nothing here
touches P0-A, P0-B, P0-C or the Brightmoor rework.

**No account is named in this document.** The 32 are real prospects, `work/`
is gitignored for that reason, and this file is in git. Accounts are referred
to by the first eight characters of their account key, which an operator can
recompute from the domain with
`py -3 -m src.operatorexclusion --why <domain>`.

---

## 0. WHAT THIS DOCUMENT CLAIMS, AND WHAT EACH CLAIM RESTS ON

Every claim below carries CLAIM / AUTHORITY / MEASURED AT / STATE. A test
count is not a PASS and does not appear as one.

---

## 1. THE DEFECT — REPRODUCED, NOT ASSUMED

**CLAIM.** The TASK-430 prohibition did not hold. 32 companies were recorded
as never to be enrolled again; after a company-fact refresh, 7 stay `rejected`
and **25 revert to `review_required`**.

**AUTHORITY.** `qualify.state_of` (canonical resolver per OPERATING-MODE §0a)
run over the 32 records, read from a byte-identical copy of
`work/queue.jsonl`.

**MEASURED AT.** 2026-09-28, queue sha256
`dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2`.

**STATE. VERIFIED.**

    the 32 companies:        32       records found in queue:  32
    records carrying human_review: 32
      by:        {'Zvonimir (operator) 2026-09-28': 32}
      decision:  {'reject': 32}
      at:        ['2026-09-28T10:38:17+00:00']
      fingerprint still matches: {True: 32}

    qualify.state_of TODAY                   {'rejected': 32}
    classifier verdict on the record         {'review': 25, 'rejected': 7}

    -- move inputs_fingerprint, as any fact refresh does --
    qualify.state_of AFTER                   {'review_required': 25,
                                              'rejected': 7}
    classifier verdict on the record         UNCHANGED
    dmplan.human_review() returns None for   32 of 32
    qualify.review_of() returns None for     32 of 32

**THE MECHANISM.** `dmplan.human_review` and `qualify.review_of` both drop a
review whose `inputs_fingerprint` no longer matches the qualification's. That
rule is **correct for a review that PERMITS** — an accept given on Monday must
not authorise spending on Tuesday's different company — and **exactly
backwards for one that FORBIDS**. The 7 survive only because the classifier
itself independently says `rejected`; they were never being held by the
ruling. So the fix is not a weakened staleness rule. It is a separate state.

---

## 2. REUSE WAS EVALUATED FIRST. NONE OF THE THREE CANDIDATES FITS.

**STATE. VERIFIED** (by reading each mechanism's definition and its callers).

### `src/agencydnc.py` — the agency-wide do-not-contact. REJECTED, four reasons.

1. **It is keyed on strong PERSON identity only.** `agencydnc.keys_for` builds
   keys from an email and a LinkedIn URL and deliberately refuses to look at
   anything else. The 32 are companies; several carry no contact at all,
   because a company that did not qualify consumes zero person credits by
   policy. A person-level key cannot express "this account", and cannot reach
   a decision maker discovered next month.
2. **Its privacy model forbids the metadata this state must carry.** Its own
   docstring: *"No name. No company. No workspace... a free-text note is where
   somebody eventually writes 'replied to Productive'."* WHO decided and WHY
   is exactly what an operator exclusion has to answer. Extending it would
   break the property it exists to have.
3. **It is suppression.** `NOTICE = "suppressed by agency safety policy"`. The
   operator was explicit that a prospect who unsubscribed and a company we
   refuse to sell to are different facts with different reversibility.
4. **It has no lift path at all** — append-only, no removal — so it cannot
   record an operator reversal either.

### `ingest.load_suppress()` — the domain suppression list. REJECTED.

Right shape (company level, read on the send path) and wrong content. It
returns a **`set` of bare domain strings**: no `by`, no `at`, no reason, no
origin, and no room for any across its twenty-odd call sites. And its content
is the **client's own customer roster** — `config/suppress.local.txt`, which
`ingest` describes as *"the roster of who is paying us"*. A customer who
churns comes off that list; an operator policy does not. Merging the two would
destroy the origin distinction the operator called load-bearing, and would put
operator policy in a file the client's account team edits.

### `accountstate.DO_NOT_CONTACT` / `record["do_not_contact"]`. REJECTED.

A **reporting vocabulary** — `accountstate`'s docstring says it is for *"the
Monday Slack post, the PDF and later the portal"* — and **no send gate reads
it**. `record["do_not_contact"]` is a bare boolean with no who, when or why,
and `accountpolicy.ACCOUNT_DNC` means *"Somebody asked us to stop contacting
the company"*: a fact about their wishes, not ours. Decisive objection: it
lives **on the record**, and a queue record is precisely what a migration, a
re-ingest or a batch reprocess rewrites.

### THE DECISION: a new canonical state, `src/operatorexclusion.py`.

Deliberately thin — one file, one lookup, one vocabulary — and every reader
calls it rather than re-deriving anything.

---

## 3. THE MECHANISM

    classifier verdict   qualification.verdict.icp_status   UNTOUCHED
    human review         qualification.human_review         UNTOUCHED,
                                                            still goes stale
    permanent exclusion  config/operator-exclusions.jsonl   NEW

**The exclusion is NOT stored on the record.** `exclusion_of(rec)` hashes the
record's domain and looks it up in the register. Nothing on a queue record is
trusted. That is what makes "no automated path may clear it" structural rather
than asserted: a fact refresh, a requalification, a fingerprint change, a
batch reprocess, a queue migration and a re-ingest all rewrite records, and
the answer does not live there.

**Why the register is in git, and why the account is hashed.** Two repository
rules pull opposite ways: OPERATING-MODE — *"a gate whose only evidence lived
in a gitignored directory fails open on a clean clone"*; CLAUDE.md — *"work/
stays gitignored... not ours to publish."* Resolution, the one `agencydnc`
already made: **commit a one-way hash of the account alongside cleartext
decision metadata, which is not identifying.** The register reaches every
clone; the roster does not. This is not encryption and is not claimed to be —
somebody holding the file and a candidate domain list can test each one,
exactly as `agencydnc.fingerprint` states about itself. What it buys is that
the file is not a directory of a client's prospects.

**The row.**

    {"op": "exclude",
     "account":   "<sha256 of domain:<normalised domain>>",
     "origin":    "operator_policy",
     "by":        "Zvonimir (operator)",
     "at":        "2026-09-28",
     "reason":    "would not pass the ICP gate on the TASK-430 audit ...",
     "authority": "operator decision B, Zvonimir, 2026-09-28, ...",
     "task":      "TASK-430"}

**Reversibility.** Append-only log of `exclude` and `lift`. `lift()` is
operator-only and three things enforce it:

1. the exclusion is not on any record, so record-rewriting paths cannot reach it;
2. `lift()` requires `confirm=<the account key>` — a batch loop cannot supply
   that by accident;
3. **nothing in `src/` calls `lift()`**, asserted by an AST walk over every
   module, and the register's bytes are asserted unchanged after every
   automated path runs.

A `lift` whose `authority` is not `operator` is refused at write time **and
ignored at read time**, so a row that reached the file by an editor, a script
or a bad merge takes no effect either.

**The write barrier.** `store.refuse_production_write` guards `work/` and does
not cover this file. `operatorexclusion._append` therefore carries its own:
under test, an append to the tracked register raises
`ProductionRegisterUnderTest`.

---

## 4. THE REGISTER AS RECORDED

**CLAIM.** 32 accounts, all `operator_policy`, all by `Zvonimir (operator)`
dated `2026-09-28`, task `TASK-430`.

**AUTHORITY.** `py -3 -m src.operatorexclusion` read in a **fresh process**.

**MEASURED AT.** 2026-09-28. **STATE. VERIFIED.**

    operations               32
    excludes                 32
    lifts                     0
    active                   32
    unreadable_rows           0
    active_set_fingerprint   b87d4f50c942028e
    origins                  operator_policy
    by                       Zvonimir (operator)
    tasks                    TASK-430

Written by `scripts/record_task430_operator_exclusions.py`, which derives the
identities from `work/TASK-430-icp-verdicts-2026-09-27.json` rather than
hand-typing them, and is idempotent. No plaintext domain or company name
appears in the register — asserted by a test.

---

## 5. PROVEN AT EVERY PATH — TEN PATHS, SEVENTEEN CHECKS

**CLAIM.** Every path capable of moving an account toward outreach refuses.

**AUTHORITY.** `scripts/verify_operator_exclusion_paths.py`, run against real
production records loaded from a copy of `work/queue.jsonl`. Subject: **one of
the 25 whose CLASSIFIER verdict is `review`** — the operator's own acceptance
case — account key `08e41a12…`.

**MEASURED AT.** 2026-09-28. **STATE. VERIFIED, 17 of 17.**

| # | Path | The function that refuses | What it returned |
|---|---|---|---|
| 1 | qualification / enrolment | `qualify.state_of` | `'operator_excluded'` |
| 2 | person enrichment | `dmplan.may_enrich` | `False, "permanently excluded by operator policy…"` |
| 2 | person enrichment (spend path) | `enrich.person_level_allowed` | `(False, 'operator_excluded')` |
| 3 | email eligibility | `channels.email_verdict` | `(False, 'operator_excluded')` |
| 4 | LinkedIn eligibility | `channels.linkedin_verdict` | `(False, 'operator_excluded')` |
| 5 | campaign planning / send gate | `eligibility.must_not_contact` | first reason `'blocked:operator_excluded'` |
| 5 | campaign launch blocker | `campaigns.check_no_operator_excluded_accounts` | `False, "1 account(s) are permanently excluded…"` |
| 5 | the send-step decision | `eligibility.decide` | `blocked / blocked:operator_excluded` |
| 6 | SequencePlan (build) | `sequenceplan.new` | `PlanRefused` |
| 6 | provider projection, EmailBison | `sequenceplan.derive_bison_payload` | `PlanRefused` |
| 6 | provider projection, HeyReach | `sequenceplan.derive_heyreach_payload` | `PlanRefused` |
| 6 | staging sequence gate | `sequencegate.check` | failure `qualified`: *"qualification is operator_excluded: this sequence should not exist"* |
| 7 | retry / reprocess | `revival.assess` | `never: the operator has permanently excluded this account` |
| 8 | fact refresh | `refresh.excluded` | `'operator_excluded'` |
| 9 | requalification | `qualify.state_of` after `qualify.company` | `'operator_excluded'`; classifier still `'review'` |
| 9 | requalification, drop release | `qualify._release_stale_icp_drop` | `None`; record stays `dropped` |
| 10 | regeneration | `run.stage_generate` | `records=0`, stage `refused` |

Two of these are reached by many more callers than the table suggests, and
that is why they were chosen. `eligibility.must_not_contact` is consulted by
`eligibility.decide` (both channels), `eligibility.for_record`,
`plan.execution_plan`, `executionguard.authorize`, `executionguard.revalidate`
and `leadstop.sweep`. `qualify.state_of` is what `bisonfactory` hands to
`sequencegate.check` on the staging path, and what `enrich.icp_state` asks
before any person credit is spent. `BLOCKED_OPERATOR_EXCLUDED` is also named
in `executionguard.SUPPRESSION_REASONS` and in both of
`nextaction`'s terminal-reason sets.

### The control, run in the same pass

A record identical in every field except its domain, which the register has
never heard of:

    blocks               False
    state_of             'rejected'          (its human review, not this)
    email_reason         'verification_not_sendable'
    linkedin_reason      None
    must_not_contact     None
    refresh              None
    revival_why          'nothing has been sent to this account yet'

**No path attributes its refusal to the exclusion.** A gate that refuses
everything would prove nothing about this one.

---

## 6. THE CRITICAL NEGATIVE CONTROL — ALL FOUR STEPS

**Subject:** one of the 25 whose classifier verdict is `review`, account key
`08e41a12…`. **STATE. VERIFIED.**

### Step 1 — before the refresh: BLOCK

    classifier verdict      'review'
    inputs_fingerprint      '7ca6dae3723dccba'
    human_review fp         '7ca6dae3723dccba'   (matches: True)
    qualify.review_of       a live review
    qualify.state_of        'operator_excluded'
    permanent exclusion     BLOCK

### Step 2 — change the company facts so the fingerprint moves

    new inputs_fingerprint  '7bbc4d458937e866'   (moved: True)

Asserted, not assumed: the script raises if the fingerprint did not move.

### Step 3 — after the real refresh path (`qualify.company`): still BLOCK

    classifier verdict now  'review'   (was 'review')   <- may legitimately change
    qualify.review_of       None - STALE, as designed   <- may legitimately go stale
    qualify.stale_review_of present
    dmplan.human_review     None - STALE, as designed
    qualify.state_of        'operator_excluded'
    permanent exclusion     BLOCK

    every path re-asked:
      state_of             'operator_excluded'
      email                (False, 'operator_excluded')
      linkedin             (False, 'operator_excluded')
      must_not_contact     'blocked:operator_excluded'
      may_enrich           False
      refresh              'operator_excluded'
      revival              'never'

**And all 32, not one.** The same refresh-and-re-ask was run over every
account in the register, against four independent gates:

    accounts swept                          32
    classifier verdicts BEFORE the refresh  {'review': 25, 'rejected': 7}
    classifier verdicts AFTER  the refresh  {'review': 25, 'rejected': 7}
    WITHOUT the register, state would be    {'review_required': 25,
                                             'rejected': 7}   <- the defect
    WITH the register, exclusion held on    32 of 32 at all four gates

### Step 4 — THE BYPASS. Remove the check from one downstream path; the test must FAIL.

**Mutation.** In `src/eligibility.py`, `must_not_contact`'s first element was
replaced by `None`, deleting the `_operator_excluded(rec)` call and nothing
else.

**The hermetic suite went red, 3 of 40:**

    FAIL test_5_campaign_planning_and_the_send_gate
         AssertionError: None != 'blocked:operator_excluded'
    FAIL test_after_the_refresh_every_path_still_blocks
         AssertionError: None != 'blocked:operator_excluded'
    FAIL test_5b_the_step_decision_blocks
         AssertionError: 'blocked:lint_failed' != 'blocked:operator_excluded'

**Failed for the intended reason, and a different guard did NOT fire first at
the mutated function.** `must_not_contact` returned `None` — nothing else on
that list caught the account. That is the check the operator asked for, and it
passed.

**THE THIRD FAILURE IS THE FINDING WORTH KEEPING.** At `eligibility.decide`, a
*different* guard did fire: `blocked:lint_failed`. On the **real production
record** the substitute guard was `held:verification_unknown` — a **HELD, not
a BLOCK**. Held is a queue to work through; supply a verification and the step
proceeds. So on real data, deleting that one line moves the account from
permanently blocked to reachable, and **a test that asserted only "blocked"
would have stayed green through the mutation.** These tests assert the reason
CODE, which is why they went red.

**The real-data verification went red in the same run:**

    5. campaign planning / send gate   eligibility.must_not_contact
       *** DID NOT REFUSE ***: first reason None
    5. the send-step decision          eligibility.decide
       *** DID NOT REFUSE ***: held / held:verification_unknown
    STEP 3 RESULT: the permanent exclusion *** FELL OFF ***
    PATH CHECKS: 15 of 17 refused
    VERDICT: FAILED

**Restored byte-identical.**

    before  b9e82e7d0fb70afdedef43dd0ea4870bf0970808132221328884d78999ca9bea
    after   b9e82e7d0fb70afdedef43dd0ea4870bf0970808132221328884d78999ca9bea
    cmp against the pristine copy: identical

Both artifacts returned green after restoration: 40/40 hermetic, 17/17 paths.

---

## 7. THE INVERSE TEST — NOTHING SILENTLY REMOVES IT

**CLAIM.** No change to classifier evidence and no fact refresh removes a
permanent operator exclusion. **STATE. VERIFIED.**

Proved as a **file hash**, not an assertion about intent: if no automated path
can change the register's bytes, no automated path cleared an exclusion.

    register sha256 before / after the whole verification run: identical
    exclusion still active: True
    by / at unchanged: 'Zvonimir (operator)' / '2026-09-28'

Under the hermetic suite the same hash is taken around
`qualify.state_of`, `qualify.company`, a full fact refresh,
`refresh.excluded`, `revival.assess`, `dmplan.may_enrich`,
`enrich.person_level_allowed`, both channel verdicts,
`eligibility.must_not_contact`, `run.stage_generate` and
`campaigns.check_no_operator_excluded_accounts`. Byte-identical.

Four further inverse cases, each its own test:

- **The classifier turning `qualified` does not lift it.** Verdict flipped to
  `qualified`, human review removed entirely: still `operator_excluded`, and
  `enrich.person_level_allowed` still `False`.
- **Wiping the record's `qualification`, `company_facts` and `research`
  entirely changes nothing** — the exclusion is not stored there.
- **A `lift` row whose authority is not `operator` lifts nothing**, even when
  written directly into the file.
- **`lift()` without the correct `confirm` key is refused**, and no module in
  `src/` calls `lift()` (AST walk over every module).

And the control on the whole exercise: with the register removed, the
hermetic subject reproduces the original defect —
`review_of` → `None`, `human_review` → `None`,
`state_of` → `review_required`.

---

## 8. INSPECTABILITY — DEMONSTRATED ON A REAL RECORD

`operatorexclusion.explain(rec)` answers WHY / WHO / WHEN / WHAT REASON /
WHICH ORIGIN, and reports the four origins separately with their four
different reversibility rules. Taken on the real subject **after** the fact
refresh (domain and company redacted here only):

    permanently_excluded: true
    account_key:          08e41a12…

    origin: operator_policy        blocked: true
      who:            Zvonimir (operator)
      when:           2026-09-28
      reason:         would not pass the ICP gate on the TASK-430 audit of
                      campaigns 491-500 and the operator ruled the account
                      must never be enrolled again; the classifier verdict
                      and the human review are unchanged and this exclusion
                      does not depend on either
      authority:      operator decision B, Zvonimir, 2026-09-28, recorded in
                      docs/PERMANENT-OPERATOR-EXCLUSION-2026-09-28.md
      task:           TASK-430
      reversibility:  lifted only by an explicit operator action recorded
                      with who, when and why
      history:        [exclude by Zvonimir (operator) at 2026-09-28]

    origin: human_review           blocked: false    stale: true
      who:            Zvonimir (operator) 2026-09-28
      when:           2026-09-28T10:38:17+00:00
      reason:         NOT_QUALIFIED by operator decision 2026-09-28. TASK-430
                      ICP audit of campaigns 491-500; ... Recorded so this
                      company can never be enrolled again. A verdict recorded
                      today does not make any past send retroactively approved.
      reviewed_status: review
      reversibility:  bound to one version of the evidence; goes stale when
                      the evidence moves
      why:            a human rejected an EARLIER version of the evidence;
                      this review is stale and authorises nothing

    origin: classifier             blocked: false
      who:            src/qualify.py:company -> src/icp.py:score
      icp_status:     review        icp_tier: REVIEW    icp_confidence: low
      reason:         the two criteria that decide what kind of company this
                      is are not both established; unknown: company_type,
                      services_business, tracks_time; ...
      reversibility:  re-derived from evidence; a better verdict may change it

**This is the load-bearing output.** Three origins, three reversibility rules,
one still blocking. The classifier still says `review`, exactly as the
operator required. The human review is shown stale rather than deleted — it
records a true fact and keeps recording it. `qualify.dossier` carries
`operator_exclusion` alongside `human_review` and `stale_human_review`, so the
review screen shows all three.

`py -3 -m src.operatorexclusion` prints the register naming nobody;
`--why <domain>` answers for one account.

---

## 9. SAFETY

- **PROVIDER WRITES = 0.** `urllib.request.urlopen` (the single outbound call
  in `src/providers/__init__.py`) and `providerwrites.perform` were both
  booby-trapped. **Both traps were fired deliberately first**, so they are
  proven to work, and the whole verification then ran under them:
  *deliberate firings 2; attempts during the verification 0*. No existing
  campaign was read, touched or named.
  **AUTHORITY.** the interceptor ledger, with the interceptor proven to fire.
  **STATE. VERIFIED.**
- **Production store untouched.** `work/queue.jsonl` backed up before any
  work; sha256 identical before and after
  (`dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2`), mtime
  unchanged. Every run used a byte-identical copy via `$QUEUE`. Nothing in
  this work calls `store.save`.
- **The freeze is respected.** `killswitch.workspace_state('productive')` →
  `{'sending': False, 'why': 'sending.live is off for productive'}`, read with
  `WORKSPACES` pointed at production's `work/workspaces.jsonl`. **Worth
  recording because it nearly became a false PASS:** asked from inside the
  worktree, which has no `work/` of its own, the same call returns
  `sending: False` with `why: 'no such workspace: productive'` — the right
  answer for the wrong reason, and per invariant 0 that is UNKNOWN, not a
  verified freeze. Nothing here sends, enrols, activates or attaches.
- **The register was read back from a FRESH process**, not from the process
  that wrote it.

---

## 10. WHAT IS NOT CLAIMED

- **The register's rung is `INTEGRATION_TESTED`, not `LIVE_VALIDATED`.** It
  has been proved against real production records through real production
  entrypoints, with the provider untouched. No live provider run exercised it,
  because none may under the freeze.
- **The hash is not encryption.** Somebody holding the register and a
  candidate domain list can test each one. Identical trade to `agencydnc`,
  stated for the same reason.
- **The 32 are not sendable today anyway.** Per OPERATING-MODE §0c both halves
  are reported: their current qualification refuses them, **and 18 of their
  contacts were already emailed, all in campaign 491.** This state changes the
  first and says nothing about the second. A verdict recorded today does not
  make a past send retroactively approved.
- **`config/operator-exclusions.jsonl` is new tracked state.** It is small,
  append-only and hashed, but it is a file somebody could edit. The guards are
  the read-time authority check on `lift` and the tests; there is no signature
  on the rows. Adding one is follow-up work, not something to assume.

---

## 11. FILES

    src/operatorexclusion.py                        NEW - the state
    config/operator-exclusions.jsonl                NEW - the register (32)
    scripts/record_task430_operator_exclusions.py   NEW - derives the register
    scripts/verify_operator_exclusion_paths.py      NEW - the ten-path proof
    tests/test_a_permanent_operator_exclusion_survives_a_fact_refresh.py  NEW

    src/qualify.py        state_of; _release_stale_icp_drop; dossier
    src/dmplan.py         OPERATOR_EXCLUDED state; may_enrich
    src/channels.py       OPERATOR_EXCLUDED reason; both channel verdicts
    src/eligibility.py    BLOCKED_OPERATOR_EXCLUDED; must_not_contact
    src/campaigns.py      check_no_operator_excluded_accounts, in CHECKS
    src/sequenceplan.py   new; derive_bison_payload; derive_heyreach_payload
    src/sequencegate.py   BLOCKING_QUALIFICATIONS
    src/refresh.py        excluded
    src/revival.py        assess
    src/run.py            stage_generate
    src/executionguard.py SUPPRESSION_REASONS
    src/nextaction.py     TERMINAL_CONTACT_REASONS; ACCOUNT_TERMINAL_REASONS

No file listed as another agent's was touched: `src/generate.py`,
`src/generate_campaign.py`, the signature/sender-identity modules,
`tests/task425fixture.py` and every reserved document are unmodified.
