# OPERATING MODE — the only currently-effective rules

**First operational document after `CLAUDE.md`.** Per vertical-slice §29 this
carries **only what is in force now**. Historical directives stay immutable and
auditable; they are referenced, not copied.

Governing document: **`docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md`**,
sections 0–40 plus the final principle, complete and verbatim. **Where it differs
from an earlier standing order, it wins.**

---

## CURRENT OBJECTIVE

> STOP EXPANDING THE ARCHITECTURE AND FINISH THE FIRST PRODUCTION-REALISTIC
> VERTICAL SLICE.

The test for every new task (final principle): **does this get us from canonical
client knowledge to a verified, provider-ready, account-level Email + LinkedIn
outreach plan?** If no, it goes to `docs/BACKLOG.md` unless it is a P0
safety/correctness issue.

Phase 1 success is defined by the **34-point acceptance scenario in §32**, on one
qualified account with 2–3 decision makers, demonstrated **through real production
entrypoints** — not mock-only paths.

## CRITICAL PATH

    CLIENT CANONICAL KNOWLEDGE → SECOND BRAIN → CAMPAIGN STRATEGY
    → APPROVED OFFER A/B → ACCOUNT → ACCOUNT RESEARCH → BUYING COMMITTEE
    → CONTACT/ROLE RELEVANCE → COPY SKILLS → EMAIL + LINKEDIN SEQUENCE
    → CROSS-CHANNEL COORDINATION → QA → CANONICAL SEQUENCE PLAN → PREVIEW
    → APPROVAL HASH → SUPPRESSION/SAFETY → PROVIDER PAYLOAD → WRITE GATE

**Live chain as of `cad7c7a4`:** Offer Engine **on master** (TASK-333 integrated) →
campaign strategy (TASK-320, running) → production wiring (TASK-321, blocked on
320). Five skills verified ready on branch, not yet integrated.

Execution order is **§37**. Do not reorder it without repository evidence.

## PRODUCTION FREEZE

`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`. **No launch, activation,
enrolment, provider attachment, prospect-facing send, resume, or
provider-changing live test without the operator's explicit APPROVED.** Existing
active production is not modified because of a directive. **493 is the only
campaign sending and stays as it is.** No live canary is authorised (§35).

## OPERATOR DECISIONS — 2026-09-27 evening, Zvonimir, ALL IN FORCE

**Recorded by Claude from the operator's own message, 2026-09-27. These close
the five open decisions the afternoon handoff carried in its section 7, and they
are no longer to be asked about.** Where one of them repeats a rule already
recorded elsewhere, the canonical record stays where it is and this section
points at it rather than copying it.

### The copy path — decisions 1 to 4, all MUST REPRODUCE

1. **Copylint retry stays.** A draft that fails copylint is REGENERATED and
   never proceeds toward sending. Never widen a lint rule to make a draft pass.
2. **A draft that failed a gate is NEVER stored as a send candidate.** Same
   defence as 1, in a different place.
3. **A model error HOLDS the record. No fail-open.** Passing silently with no
   copy is fail-open and is refused.
4. **Unapproved drafts MAY be regenerated. Approved or sent drafts are NEVER
   overwritten**, because regeneration after approval invalidates the approval
   hash. The approval hash stays bound to exactly the approved copy.

These four are `TASK-400`'s merge condition; the 9 `tests/test_generate.py`
errors map to them and are RESOLVED, never retired.

### Scope and offers

5. **`TASK-427`: `_check_offers` checks ONLY the offer selected for that
   prospect**, not every offer in the system. Measured, not assumed: `offers.
   load()` returns 8 offers, 2 approved (A and B) and 6 pending — the capability
   offers A and B compose. Iterating the library therefore refuses every live
   run for productive at `OFFER-PM-001`, correctly fail-closed and pointed at
   the wrong question.
6. **Offers A v2 and B v2 stay approved as recorded.** Reaffirmed without
   change; the canonical record is `config/clients/productive-offers.yaml`,
   which already held every term as stated, and it now carries the date it was
   last confirmed. AI capabilities are supporting angles only: at most one per
   message, never required, never "AI feature first, then invent a problem".
   One licensed mechanism: a walkthrough with a Productive AE unlocking the
   premium trial including the AI features (CLIENT_APPROVED, Bruno,
   2026-09-27). The self serve 14 day trial stays
   `RECORDED_NOT_LICENSED_FOR_COPY`. No case study, figure or customer name is
   licensed while every case-study `page_text` is null. Single CTA
   `https://productive.io/get-started/`.

### Later the same evening — three more decisions, Zvonimir, 2026-09-27

7. **`CLIENT_SUPPLIED` is a sanctioned provenance class, and it licenses less
   than the pack it sits in.** Facts from Productive's own approved list (the
   09-07 CSV) MAY enter the admitted pack, recorded as `CLIENT_SUPPLIED` **with
   the source file AND the row**, and are usable for **qualification and
   strategy**. A **prospect-facing claim still needs a public source or a stored
   page — never the CSV alone.** This extends the provenance enumeration below
   (VERIFIED / CLIENT_APPROVED / INFERRED / UNKNOWN) by operator decision, and it
   places `CLIENT_SUPPLIED` in the same category as `INFERRED` *for claims*: it
   may inform, it may not assert.
   **This was NOT the state of the code when decided.** `packfacts.pack_for`
   ended `admitted.extend(_ingest_facts(rec))`, putting client-CSV facts straight
   into the list `copylint` licenses claims from, with no `identity_of()` and no
   row recorded — so an unverified spreadsheet figure could ground a
   prospect-facing assertion. Implementing the second half of this decision is
   real work, not a rubber stamp.
   **Second half MERGED to master 2026-09-27 night** (branch
   `client-supplied-facts-cannot-license-claims`, head `08e35fa2`). `pack_for`
   now returns the claim licence and the client's own facts as two separate
   lists — see the provenance bullet under ARCHITECTURAL INVARIANTS for the
   shape — and `src/ingest.py` records the row. Proof through the real send path,
   with the provider untouched:
   `tests/test_a_client_csv_fact_cannot_license_a_claim.py`, 9/9, including its
   own control test so the gate cannot be confused with one that refuses
   everything.

   **⚠ THE DECISION IS IN FORCE ON THE PACK PATH AND ONLY THE PACK PATH.**
   `src/claims.py` is a SECOND, independent claim gate whose support model is
   every `company_facts` key and value, so **a CSV figure still licenses a
   prospect-facing claim there.** Reproduced directly, twice, before the merge:

       "You have 4000 employees."  + company_facts{headcount: 4000}  -> NO objection
       "You have 4000 employees."  with that fact removed            -> "the figure
                                      4000 appears in no stored fact"

   Six live callers (`eligibility` ×2, `executionguard`, `bisonfactory`,
   `heyreachfactory`, `generate`). **Deliberately not fixed**, because
   `company_facts` carries no per-key provenance, so excluding those six keys
   would also refuse claims a provider-sourced value legitimately supports — a
   new decision materially changing licensed claims, and therefore the operator's.
   `ISSUE-048` in `docs/state/PROBLEM-REGISTER.md`.

   **DECIDED — "B", Zvonimir, 2026-09-28. THIS IS A TEMPORARY CONSERVATIVE
   POLICY AND MUST NOT BE MISTAKEN FOR THE FINAL DATA ARCHITECTURE.**
   The six `CLIENT_SUPPLIED` company fields stay available for qualification,
   segmentation, prioritisation, strategy, offer selection and internal
   reasoning. They **MUST NOT license a prospect-facing factual claim through
   EITHER claim-validation path.** Where the only evidence for a claim is one of
   those fields, **fail closed and refuse the claim.** Neither validator may be
   weakened to make the one-account test pass.

   **B is deliberately blunt and the cost is accepted, not hidden:** because
   `company_facts` carries no per-key provenance, a claim that a
   provider-sourced value would legitimately support is ALSO refused when it
   happens to live under one of those six keys. That is erring toward refusal on
   purpose, and it is temporary.

   **The replacement is `TASK-462` (decision "A"), COMPANY FACT PROVENANCE,
   REQUIRED post-slice work, explicitly NOT to be built before `TASK-425`.**
   Provenance moves to FACT level, not field level, and the rule is: **same
   value + different provenance = different claim authority.** When it lands,
   B's six-key refusal is deleted in the SAME change — otherwise the system
   carries two answers to one question and the blunt one wins silently.
8. **The 13 stale stored cadence rows stay REFUSED. No migration.** New
   campaigns get the canonical five-plus-five. See item 9 under LAUNCH BLOCKERS
   for the measurement; the §6 reconciliation question is hereby answered and
   closed.
9. **The 786 contacts in 491-500 with no ICP verdict: classify their companies
   now** — read-only, Qwen or Groq, cost reported from the ledger, verdicts
   recorded, **the live campaigns untouched** — and report how many would not
   have qualified. `TASK-430`. **The decision about those nine campaigns goes to
   the operator afterwards and is not taken by whoever runs the classifier.**

## OPERATOR DECISIONS — 2026-09-28, Zvonimir, ALL IN FORCE

Recorded from the operator's own message. These stand alongside the 09-27 set
above and do not replace it.

### 10. UNSUBSCRIBE — THE FALLBACK IS OUR OWN READABLE TEXT

Stage (a) is done: campaign **500** carries `can_unsubscribe: true`, read back,
2 of 29 fields moved. **(b) 487/489/493 and (c) the rest stay BLOCKED** while
the operator checks the footer themselves with a test email.

**The decision that removes the deadlock:** if the rendered footer on campaign
500 **cannot be seen**, the fallback is **our own explicit `unsubscribe_text`,
which can be read back** — option (B) of section 2a. **Never an unseen footer
on 487, 489 or 493.** Option (C), proceed blind, is refused by this decision.

`unsubscribe_text` is `None` today, so the provider supplies text no API read
returns; that is why UNKNOWN was never a PASS here. Waiting on the operator's
"footer checked" before anything moves.

### 11. WEEKLY CLIENT REPORT — APPROVAL, NOT A VETO WINDOW

The approval model becomes, and no step may be skipped:

    GENERATED -> INTERNAL PREVIEW -> operator's explicit APPROVED -> CLIENT POST

**There is no veto window for client-facing content, and with no approval
nothing posts.** This replaces the thirty-minute stop window, which was a
fail-open by construction: silence released the post. **`WEEKLY_CLIENT_POST`
stays off until the approval path is built AND tested**, and the internal
preview keeps going to `#resonate-os` so a review pause never becomes a blind
spot.

### 12. CREDENTIALS — NAMES ONLY, EACH ROTATED OR ROTATION REQUIRED

Every credential that appeared in Slack, a `work/` artifact or a shared chat is
listed **by variable NAME, never by value**, and marked **ROTATED (with
evidence) or ROTATION REQUIRED**. **No cutover and no live send while any is
ROTATION REQUIRED.** The operator rotates; Claude verifies **by
authentication** after the operator says done — a set variable is not an
authenticated one, and `scripts/credential_health.py --verify` keeps the five
states apart. Names come from `config.VARIABLES` and are never guessed.

### 13. SEND LEDGER IS P0, BEFORE ANY TEN-ACCOUNT RUN

The ledger for this workspace is empty: across 681 records, **not one recorded
send event**, while EmailBison has sent. Ingesting provider send events
read-only is the fix, and its acceptance is behavioural, not a row count:

    1. `already_sent` proves TRUE on a few known really-sent contacts
    2. reconciled against the provider, not against our own copy
    3. the digest STOPS saying "no confirmed sends" while replies exist

Until those three hold, the 1,504 unplaceable accounts figure and the weekly
report both measure a blind spot rather than the estate.

### 14. CROSS-CHANNEL STOP — IMPLEMENTED, NEVER LIVE_VALIDATED

Both directions. Current state on the ladder is **IMPLEMENTED / NEVER
LIVE_VALIDATED**, and it is reported that way rather than as working.
**Design a safe live validation and bring it to the operator BEFORE running
it.** Launch blocker 4 stands until then.

### 15. NOT NOW — REFUSED UNTIL THE OPERATOR REOPENS THEM

New features · ten accounts · autonomous sending · more workers · the LinkedIn
layer · CRM · a Second Brain redesign · cadence migration · UI · backlog
clean-up.

**This is a list of things not to start, not a list of things to argue about.**
A task that serves one of them goes to `docs/BACKLOG.md` unless it is a P0
safety or correctness issue.

### 17. ISSUE-054 IS RULED — AND THE 256 STILL MAY NOT BE SENT

**Operator, Zvonimir, 2026-09-28, after reviewing a sample of twelve.**

> Sample reviewed, clean, A for the rest. Same subject across one thread is
> correct threading. These are old 3-step records: none of them, including
> times10, may be sent with this old copy.

So the ruling has **two halves and only the first one unblocks anything:**

1. **The subjects check is settled.** Five steps carrying the opener's subject
   on a one-thread cadence is what `EMAILBISON-COPY-REQUIREMENTS.md` REQUIRES,
   so the old refusal was refusing correct copy. The gate's fix stands and
   `task-425-one-account-dry-run` may merge on normal verification.
2. **The copy is NOT approved for sending.** All 256 carry old THREE-STEP
   copy, and **no contact among them may be sent with it — `times10` included,
   which is the only one of the 256 that is `sendable` and carries a provider
   lead id.** If it is ever used it goes through the NEW generation path.

**The sample was complete by copy, not a twelfth of it.** Measured
2026-09-28: across all 256 there are only **five distinct subject lines**, and
the twelve reviewed covered all five. That is why "A for the rest" rests on
more than proportion.

**WHAT BLOCKS THEM TODAY, AND IT IS NOT THIS RULING.** Verified from a fresh
read: all 256 resolve to ICP `not_processed`, so `qualify.state_of` refuses
every one at the qualification gate, and 255 of 256 are not `sendable`. **That
block is real but incidental** — it is the ICP gate doing its job, not an
enforcement of the sentence above.

**The residual risk, stated rather than left implicit:** if one of those
companies is ever ICP-qualified, the old 3-step copy becomes sendable again
and nothing structural refuses it. **This rule is RECORDED, not ENFORCED** —
IMPLEMENTED at best on the ladder, and honestly ABSENT as enforcement. Making
it structural is required follow-up work, not a thing to assume is already
true.

### 18. THE SECRET SCANNER MUST BE PROVEN, AND UNTIL IT IS, "CLEAN" IS UNKNOWN

**Operator decision, Zvonimir, 2026-09-28. Off-path, read-only work.**

**Until a scanner meets all three conditions below, "the scan came back clean"
is UNKNOWN and is never reported as evidence.** That is not pedantry: it has
already been wrong twice in one day, in two different ways.

    1. INVENTORY FROM EVERY SOURCE, NOT ONE REGISTRY.
       `config.VARIABLES` is the APPLICATION's registry.
       `secrets_checklist.INFRA_VARIABLES` is the infrastructure's. Account
       passwords are in neither. A scanner driven by one of them reports
       clean on the others.
    2. A SYNTHETIC TEST WITH A FAKE SECRET OF EVERY SUPPORTED TYPE, AND ALL
       MUST BE CAUGHT. Never real values. A detector is only known to catch
       what it has been shown.
    3. A MUTATION THAT BREAKS THE DETECTOR MUST FAIL THE TEST. If the
       detector can be disabled and the suite stays green, the suite was
       never testing the detector.

**Both failures this is written from, because the class is the same both
times.** The ingest redactor caught a ContactOut token and a password and
missed seven live provider keys in the same channel — output that looks
redacted. Then the first exposure scan enumerated one registry and reported
the rest as "no evidence of exposure", missing two keys that were in the clear
all along. **A filter must be self-tested against every value it is supposed
to catch, before the first write rather than after** — and the set it is
tested against must be the whole set, not a registry that looked complete.

### 19. THE LAUNCH GATE ORDER — RECORDED, Zvonimir, 2026-09-28

**Gates to live, in sequence. This is not the work order (decision 16); it is
what must be true before anything reaches a real person.**

    1. TASK-425 VERIFIED
    2. credential incident CLOSED
    3. send ledger RECONCILED
    4. unsubscribe VERIFIED
    5. 10-account zero-write run
    6. operator review
    7. minimal live canary

**No gate is skipped and none is inferred from the one before it.** Gate 1 is
currently NOT met: TASK-425 finished measuring on 2026-09-28 with criteria 1
and 2 BLOCKED, 3 PASSED and 4 CERTIFIED, and it is with the operator.

**THE HETZNER CUTOVER PLANNED FOR THE NIGHT OF 2026-09-28 IS POSTPONED**,
until gate 2 closes. The infra session has been told. The exposure blocks
**cutover and live sending only — not development**, and work continues on the
current keys by the operator's explicit instruction.

### 22. SUITE LOGS AND SCRATCH OUTPUT LIVE OUTSIDE THE REPOSITORY

**Recorded 2026-09-28 from a near-miss, not from a principle.**

An agent wrote its suite log into a scratch directory inside the working tree.
`tests/test_fixture_hygiene.py` scans `git ls-files --others --exclude-standard`
— **untracked files included** — so **21,000 lines of verbose test output
quoting real prospect domains (39 hits) plus a JSON dump (5 more) became part of
the corpus the hygiene guard inspects.** It invented two hygiene failures, which
is the harmless half.

**The harmful half: a `git add -A` would have committed real prospect data
harvested out of test output.** `work/` is gitignored precisely so 300 real
companies and 92 real contacts cannot be published; a log file beside the tests
is not, and it had the same content in it.

So: **suite logs, verbose run output, JSON dumps and scratch artifacts are
written OUTSIDE the repository** — the session scratchpad, or `%TEMP%`. Never a
directory inside the working tree, tracked or not.

This is the same lesson as `git add -A` near mutation tooling, which this
repository has already paid for once: the danger is not the file you meant to
add, it is everything else that happens to be sitting there.

**AND A KILLED SUITE LEAVES DEBRIS THAT BREAKS THE NEXT ONE.** Measured
2026-09-28: **94,867 `rga-*` directories** in `%TEMP%`, one per test from
interrupted runs — `tearDown` never executes when a run is killed. Every suite
run afterwards died within minutes.

    A VERDICT WITH NO "Ran N tests" LINE IS AN ABSENT MEASUREMENT,
    NOT A FAILING SUITE.

That distinction is the point. A run that dies before reporting is UNKNOWN
under invariant 0, and reading it as "the suite fails" sends the next hour to
the wrong problem. **If a suite dies with no `Ran` line: clean `%TEMP%` and
re-run before concluding anything.** Several agents lost suite runs to this on
2026-09-28 and at least three discarded runs for unrelated reasons — if you
interrupt a suite, clean up after it.

### 24. "NIŠTA POSLANO" MEANS NOTHING SENT *BY THIS WORK*

**Operator, Zvonimir, 2026-09-28. Wording rule, and it is not pedantry.**

Every status line reading **`STVARNI PROSPECTI: Ništa poslano`** means
**nothing was sent BY THIS WORK.** It has never meant, and must never be
written to suggest, that nothing was ever sent.

**Three things WERE sent, to real people, and they stay on the record:**

    503/504/505   64 emails carrying another agency's pitch, signed with the
                  operator's name
    2026-09-23    77 emails with an empty subject and a `<p></p>` body;
                  76 recipients suppressed, four replied to a blank email
    2026-09-23    a LinkedIn message sent SEVEN MINUTES AFTER a prospect
                  replied "no thank you"

And separately: campaign 487 was recorded as having sent 0 while the provider
said 6, because the send ledger was empty and nothing ingested the provider's
events — **912 provider-confirmed sends against one recorded touch.**

**Never describe the estate as "nothing ever sent".** A status that says
"nothing sent" while three incidents reached real people is not reassurance, it
is a false statement that an operator will act on. Say which claim is being
made: *this work sent nothing*, and the historical incidents are recorded
elsewhere and unchanged.

### 23. THE BUDGET RULE — PERMANENT, Zvonimir, 2026-09-28

**Claude capacity is a budgeted resource, like API credits.**

    AT MOST 20-25% of a weekly Claude allowance goes to AUDIT AND REVIEW.
    THE REST is reserved for CRITICAL-PATH IMPLEMENTATION AND INTEGRATION.

**Never again several parallel Claude threads investigating the system while
the basic vertical slice does not exist.**

Recorded from the week it was violated. A whole weekly allowance went on
audits, reviews, verifier work and framework building — much of it producing
genuinely valuable findings — **and the one thing the operator asked for, a
single reviewable artifact for one real account, did not exist at the end of
it.** Correct findings are not the product.

**Reserve expensive independent verification for boundaries where a mistake
causes:**

    a real provider write · a real prospect send · an incorrect approval
    suppression/unsubscribe failure · credential exposure
    irreversible production state

**Everything else gets normal engineering tests, not a verification
bureaucracy.** For ordinary implementation defects: Qwen implements, the
deterministic tests run, and the work continues. **Do not create independent
Claude audits for ordinary implementation work.**

### 25. WHAT MAKES THE ONE-ACCOUNT ARTIFACT ACCEPTABLE

**Operator, Zvonimir, 2026-09-28.** The artifact is the product milestone. It
is **not** evidence of production safety until all three hold:

    the rendering chain   560 -> 904 -> 905 -> 906   verified
    TASK-564              the provider write surface, INDEPENDENTLY verified
    TASK-565              the incident regression fixtures, verified

**Until then the artifact may be reviewed, but it may NOT be described as
production-safe, canary-ready, or accepted.** Producing readable copy and
being safe to send are two different claims, and this project has conflated
them before.

**Nothing resumes, activates, enrols, attaches or sends without an explicit
operator `APPROVED`.** No ten-account run, no live canary, no campaign resume,
no enrolment, no prospect-facing provider write. `sending.live` stays false and
the freeze stands.

### 20. THE FOCUS RULE — PERMANENT, Zvonimir, 2026-09-28

**The critical path is the only thing that gets active attention.**

Any new finding that is **not on the critical path** and **not a live safety
risk** is:

    1. filed as a task, with severity and evidence
    2. reported in the next status in ONE LINE
    3. NOT turned into a new work stream
    4. NOT turned into an operator question

**The operator receives only two things:** decisions that block the critical
path or change safety, and the artifacts they review. **Do not open a new
thread without applying that test first.**

This exists because a session that reports everything it finds converts a
critical path into a list, and a list has no end. Discipline here is not
indifference to the findings — a filed task with evidence is preserved; an
unfiled one raised in conversation is lost.

**CURRENT CRITICAL PATH:**

    P0-B  ->  P0-C REAL ACCOUNT  ->  TASK-425 rerun  ->  operator review

Canonical projection integration (P0-E,
`docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md`) follows P0-B.

### 21. TASK-425 STATUS — the operator's corrected wording, 2026-09-28

    criterion 1  causal matrix                    BLOCKED
    criterion 2  signature chain                  TESTING
    criterion 3  offer sequencing + negative test  PASS
    criterion 4  claim/message audit              UNPROVEN

**Criterion 4 is UNPROVEN until the verifier proves it checks the ACTUAL FINAL
RENDERED CLAIMS, not the existence of audit fields.** It had been reported as
CERTIFIED; the operator downgraded it. "Certified" means verified against the
claims in the copy — never against field presence.

**Do not change TASK-425 to fit the system; change the system to meet
TASK-425.** No acceptance criterion may be altered. Criterion 1's clarification
is a clarification and not a loosening: the same person must get a comparable
A/A2/B/C/D set under the **normal production regeneration policy and its retry
limit, with no manual help** — otherwise it BLOCKS. A2 must show the same
selected offer, primary problem, capabilities, licensed facts, step objectives
and angle, wording free to vary; B, C and D must each change **exactly** the
dimension intervened on.

**P0-C is ONE real company from the ~30k-domain source file** and proves the
chain: source domain → qualification → research/evidence → persona → Offer A/B
→ generation → gates → provenance → SequencePlan → signature → provider
projection. **It does NOT require 2-3 decision makers** unless an approved
P0-C criterion says so, and it must **not** be a synthetic fixture — fixtures
remain regression tests only.

### 16. THE ORDER, AND IT IS NOT REPRIORITISED BY ANYTHING BELOW IT

    1. TASK-425 result, then STOP for the operator's review
    2. send ledger (decision 13)
    3. cross-channel stop validation DESIGN (decision 14)
    4. ten accounts — only after the operator's review

**The freeze stays. Provider writes only as explicitly approved.**

### SAFETY — the killswitch is ENGAGED

**`sending.live` is `off` for `productive`.** Set 2026-09-27 17:31 UTC through
`workspaces.set_policy`, actor `Zvonimir (operator) 2026-09-27`, audited under
`workspace.policy_changed`. Authority for the current value is
`killswitch.workspace_state('productive')`, never this line.

It was turned on only after its scope was proved, because the two halves are
different claims and conflating them is how an operator comes to believe a
switch does something it cannot:

- **WHAT IT DOES.** Every new provider write asks
  `killswitch.workspace_state(client)` first and refuses when it is off —
  `heyreachfactory.ensure_leads` gate 1, `bisonfactory._ensure_leads`, and
  `executionguard` at staging, granted activation and authorize.
- **WHAT IT CANNOT DO.** It cannot touch 487, 489 or 493. It is read when THIS
  system tries to START an action; the provider's own scheduler does not read
  it. `executionguard` says so at its stoppability gate: *"The killswitch
  refuses to START an action. It cannot END a campaign that is already
  running."* **Turning it off is not a pause and is never reported as one.**

Proof, `tests/test_sending_live_off_blocks_only_our_new_writes.py`, 6/6, with
the provider transport booby-trapped so a refusal arriving after a network call
fails the test instead of passing quietly. Mutation performed: gate 1 disabled
in source, three tests failed for the intended reasons, source restored and
verified. Real dry run on the production store against the canonical campaign
bound to EmailBison 487 — LinkedIn write REFUSED by name by the killswitch,
provider requests 0, 487/489/493 `approved` before and after, unchanged.

**Three independent protections now stand: the freeze, the killswitch, and
review approval.** Independent is the point — none of them is the others' backup.
No canary and no new provider write until the operator replies with an explicit
`APPROVED`.

### Execution

- **The critical path is implemented by Claude subagents (Opus)**, each in its
  own worktree, one acceptance check each, no two on the same file, pushing at
  every meaningful commit. Order: `TASK-426` → `TASK-364` rework → `TASK-400` →
  GLM verification → `TASK-425` one-account dry run → **STOP for operator
  review**. Claude also takes the 138-result integration queue and any Qwen task
  that is stuck, reworked twice, or blocking the critical path.
- **Qwen keeps only independent off-path work**: failure taxonomy, audits,
  reports, backlog.
- **GLM stays the independent verdict against branch head SHAs, and it goes
  FIRST.** A valid GLM PASS means merge. If GLM has not returned within 45
  minutes: Claude verifies independently AND a second Claude subagent reviews the
  exact branch head — **merge only if BOTH support the acceptance criteria.**
  A verdict naming no branch head SHA is VOID. **A TIMEOUT IS NEVER A PASS**
  (operator, 2026-09-27): the 45 minutes buys a different route to a verdict, not
  permission to skip one.
- **Every branch reaching REVIEW gets a GLM verdict dispatched against its exact
  head SHA immediately, and the next one is queued.** Standing rule, operator,
  2026-09-27 night. Ready depth stays at least the number of workers, with one
  task queued behind each; refill from REAL work only — the ICP audit,
  `TASK-423`, `TASK-424`, the workforce report, verification of the integration
  queue, the standing backlog. **Never an invented task, and never critical-path
  implementation** (`TASK-364`, `TASK-400`, `TASK-425` stay with Claude).
  Note when reading ready depth: a TODO file whose result already sits on a
  branch is NOT claimable work, so a deep TODO directory and a ready depth of
  zero are consistent — that is the integration bottleneck, not an empty backlog.

### DRY RUN IS NOT A SHORTCUT PAST THE SAFETY PATH

**Operator definition, 2026-09-27 night, and it is now the rule:** a dry run
means **"execute the real decision and safety path without provider writes"**. It
NEVER means "skip the safety path because `live=false`".

This is currently violated. `bisonfactory.stage()` returns before both
`_refuse_copylint` and `_refuse_sequence_gate` when `live=False`, so a zero-write
run never runs the sequence gate at all. It must: the gate executes, a bad
sequence is REFUSED, a valid sequence proceeds to the dry-run projection, and
provider writes stay exactly zero. Until that holds, a dry run cannot satisfy
`TASK-425` acceptance criterion 3, and a green dry run is evidence of less than
it appears to be.
- **The old "save Claude tokens" rules are lifted for the critical path.**
- **Do not ask the operator to reconfirm a decision already approved.** If
  implementation discovers a NEW decision that materially changes safety,
  prospect-facing behaviour, licensed claims, provider state, approval semantics
  or the `TASK-425` acceptance criteria, stop ONLY that path and ask in
  `#resonate-os` in the decision format. Unrelated safe work continues.

## KOMUNIKACIJA S OPERATEROM — trajno pravilo

**Operaterova odluka, 2026-09-27. Vrijedi nakon `/clear`, u svakoj budućoj sesiji,
za Slack agenta i za sve statuse.**

1. **Operator updates i statusi pišu se na hrvatskom.** Tehnički identifikatori
   ostaju kakvi su u kodu i ne prevode se: imena testova, putanje datoteka, SHA-ovi,
   imena taskova, imena polja i naredbe.
2. **Odluke se traže jedna po jedna, u formatu 🔴 TREBAM TVOJU ODLUKU**, i svaka
   nosi preporuku s obrazloženjem. Nikada više odluka u jednom bloku, jer se tada
   odgovori na prvu i ostale se izgube.
3. **Svaka tvrdnja o stanju imenuje svoj autoritet** (vidi "State is explicit,
   never inferred" niže). To je jezično neutralno i vrijedi i na hrvatskom.

### OPERATER FEED (`#resonate-os`) — trajni standard, 2026-09-27

Hrvatski, jezik vlasnika, bez žargona. **Nikad** brojevi linija, imena
funkcija, SHA-ovi (osim kad su potrebni za odluku), detalji test frameworka.
Tehnički detalj ide u GitHub i u handoff. Update **samo kad se nešto značajno
promijeni**, ili otprilike jednom na sat dok posao traje — nikada jedan po
malom tasku.

**SVAKA TVRDNJA O STANJU NOSI ČETIRI POLJA. Operaterova odluka, 2026-09-28.**
Ovo je feed-instanca invarijante 0 (REALITY IS NOT EVIDENCE ABOUT REALITY) i
vrijedi za svaki update, uključujući hrvatske:

    CLAIM        što se tvrdi, jednom rečenicom
    AUTHORITY    koji kanonski autoritet je to rekao, imenom
    MEASURED AT  kad je mjereno
    STATE        VERIFIED / UNPROVEN / UNKNOWN

`UNKNOWN` se nikad ne piše kao PASS, nula, prazno, idle, gotovo, sigurno ni
spremno. Tvrdnja bez autoriteta ne ide u feed.

**BROJEVI U NASLOVU NOSE SVOJE TOČNO IME FAZE**, nikada golo "ready":
`COPY_READY`, `COLLISION_CLEAR`, `PROVIDER_READY` i tako dalje. "500 spremnih"
ne znači ništa dok ne kaže spremnih za ŠTO — a razlika između "copy je
napisan" i "provider bi ovo prihvatio" je cijela razlika između demonstracije
i posla.

Svaki veći update završava ovom listom, a **kvačice se stavljaju samo iz
stvarnog stanja stroja**, nikad iz namjere:

    PUT DO PRVOG PRAVOG TESTA
    [ ] Offer A/B · Backup · Slack alerting · Qwen raspodjela posla
    [ ] EmailBison blocker · Canonical SequencePlan · Novi generation path
    [ ] Safety provjera · ONE-ACCOUNT test · Moj review · 10 accounta

    TRENUTNO RADIMO: [jedna rečenica]
    SLJEDEĆE: [jedna rečenica]
    TREBAM OD TEBE: [ništa / konkretna odluka]
    STVARNI PROSPECTI: Ništa poslano. Provider writes = 0.

Odluke idu **jedna po jedna**: 🔴 TREBAM TVOJU ODLUKU, problem, opcija A,
opcija B, preporuka, zašto, odgovori "A" ili "B".

### TASK-425 ACCEPTANCE — one-account dry run, zero provider writes

Operator's criteria, 2026-09-27. A run that does not produce all four is not a
pass, and ten accounts do not follow without an explicit operator decision.

1. **Causal matrix**, same account, everything else constant. **A** original;
   **B** one fact or signal changed — angle AND copy must change; **C** persona
   economic buyer → operations — Offer A → B AND capabilities must change;
   **D** key evidence removed — the claim disappears or the lead HOLDs. Each run
   states its EXPECTED change and its OBSERVED diff. **An unexpected change, or
   no change, is a BLOCK.**
2. **Signature chain**: mailbox owner → `sender_signature` → the rendered final
   message in the provider projection. **An empty signature is a BLOCK**
   (launch blocker 3: no mailbox has a stored signature, 155 email steps render
   empty).
3. **Offer sequencing as step objectives, enforced by `sequencegate`, with a
   negative test.** A: margin visibility → quote vs burn → resource decisions
   that move margin → Report Intelligence as mechanism ONLY if it strengthens
   the angle → reframe and close. B: project visibility → time → resourcing →
   AI Time Tracking as mechanism ONLY if it strengthens the angle → one
   operational view.
4. **An audit artifact per message**: primary problem; selected offer and why;
   core capabilities; AI capability used yes/no, which, and why relevant; source
   and provenance; the exact claim licensed and where it appeared in copy. Plus
   facts with sources, strategy, full email and LinkedIn copy, copylint,
   sequencegate, the SequencePlan, both EmailBison and HeyReach projections,
   suppression, spend, and **provider writes = 0**.

Then **STOP** and post it to `#resonate-os` for the operator.

**OVO JE CLAUDEOVO ČITANJE OPERATEROVE UPUTE, NE CITAT.** Uputa od 2026-09-27
glasi "ovo pravilo upiši u docs/OPERATING-MODE.md", a samo pravilo nije bilo
izrečeno u tekstu; izvedeno je iz zahtjeva za "prvi hrvatski operator update" i za
"novi format 🔴 TREBAM TVOJU ODLUKU, jednu po jednu, s preporukom". Ako je čitanje
netočno ili preširoko, operater ga ispravlja i ova se sekcija mijenja. Zapisano je
ovako, s naznakom izvora, upravo zato što trajno pravilo izvedeno iz pretpostavke
mora biti provjerljivo, a ne nevidljivo.

## ARCHITECTURAL INVARIANTS

### 0. REALITY IS NOT EVIDENCE ABOUT REALITY — Zvonimir, 2026-09-28

**The top invariant. Operator's own words, recorded verbatim because a rule
this load-bearing must not be paraphrased:**

> Resonate OS distinguishes reality from evidence about reality. Every
> operational state has exactly one canonical authority. Tests, task files,
> branch existence, logs, timestamps, comments, expected state, and absence
> under a guessed identifier are never authorities unless explicitly
> designated. If the canonical authority cannot be read, the state is UNKNOWN.
> UNKNOWN never becomes PASS, zero, absent, idle, complete, safe or ready.

It outranks every other invariant below, and every one of them is an instance
of it. Where a later section and this one disagree, this one wins.

**THE STATUS LADDER, used everywhere a capability or a state is classified:**

    ABSENT · IMPLEMENTED · UNIT_TESTED · INTEGRATION_TESTED ·
    LIVE_VALIDATED · PRODUCTION_ACTIVE

A rung is never skipped in a report and never inferred from the rung below it.
`IMPLEMENTED` is not `INTEGRATION_TESTED`; `INTEGRATION_TESTED` is not
`LIVE_VALIDATED`; and `LIVE_VALIDATED` is not `PRODUCTION_ACTIVE`.

**THE SAFETY EVIDENCE STANDARD.** A PASS names four things:

    1. the real path exercised          which production entrypoint ran
    2. the negative control             what was proved to FAIL, so the
                                        check is known not to pass everything
    3. the killed mutation              the guard broken deliberately, the
                                        intended test red for the intended
                                        reason, source restored byte-identical
    4. the provider readback            where a provider is involved at all

**A test count is NEVER a PASS.** "13,595 tests, 124 failing against a
baseline of 128" is a debt statement and says nothing about whether any
particular guard holds. Neither is a green suite, a passing unit test, a
document saying "integrated", or an interceptor that never fired.

**Why this is the top invariant rather than a nice principle.** Every
expensive defect this project has paid for is one violation of it: a PID check
that called every live claim dead, a task-file stage read as task state, a
count of files in `TODO/` read as ready depth, a config block read as
enforcement, a passing test read as runtime integration, `created_at` read as
send order, a handoff read as the estate, and a suite verdict committed from a
run that had not finished.

### 0a. THE CANONICAL AUTHORITY REGISTRY — Zvonimir, 2026-09-28

**One question, one authority. Agents READ THIS TABLE instead of choosing a
source ad hoc**, which is how two honest reports come to disagree. The third
column is the load-bearing one: it names the plausible source that is NOT the
authority, because that is always what gets used by mistake.

| Question | THE authority | NOT the authority |
|---|---|---|
| Is this commit on the remote? | the remote SHA, after `git fetch` | a local commit, a clean tree, a push that printed no error |
| Is this branch merged? | ancestry on `origin/master` (`git merge-base --is-ancestor`) | the branch existing, a task file saying DONE, a merge message |
| Is this worker running? | the process **and** its heartbeat | a claim's recorded PID (that is the *claiming* process), commit freshness, a file in `TODO/` |
| Was this email sent? | the provider's own event or readback | our store, `docs/state/PROVIDER-CAMPAIGNS.json` (a cached read), a scheduled row, "active" |
| Is this prospect qualified? | `qualify.state_of` | `qualification.verdict.icp_status` read alone, a score, a tier, a confidence |
| Were provider writes zero? | the write-interceptor ledger, with the interceptor proven to fire | no error in a log, `live=False`, a zero request count from an interceptor never triggered |
| Is this credential valid? | an authentication attempt | the variable being set, a value present in `.env`, the operator saying they rotated it |
| Did this task criterion pass? | the final verifier artifact | a test count, a green suite, a committed summary, an earlier run's verdict |

**If the authority in column two cannot be read, the state is UNKNOWN** — and
per invariant 0, UNKNOWN never becomes PASS, zero, absent, idle, complete,
safe or ready. A report that cites column three is not evidence and is sent
back.

#### 0a-i. THE SEND LEDGER IS NOT AUTHORITATIVE FOR HISTORICAL SENDS

**Operator correction, Zvonimir, 2026-09-28.** Measured: **912
provider-confirmed sends against ONE recorded touch** in 1,582 records.
Campaign 487 read 0 sent locally and 6 at the provider.

    PROVIDER            the authority for whether a historical send occurred
    LOCAL SEND LEDGER   incomplete, unreconciled evidence

**DO NOT USE LEDGER ABSENCE TO CLAIM ABSENCE OF A SEND.** "No row in the
ledger" means *we have not recorded it*, never *it did not happen*. Every
statement about whether somebody was contacted is derived from the provider
until ingestion is implemented AND verified.

This is an **authority correction, not permission to build reconciliation
now** — that work is not on the critical path and is not started.

### 0b. THE A/A2 CONTROL IS A PERMANENT ACCEPTANCE PATTERN — Zvonimir, 2026-09-28

**Any causal test of generation carries a control run: the same inputs twice.**
Not optional, and not only for `TASK-425`.

The reason is structural. A causal claim of the form "changing X changed the
output" is evidence only if the output is stable when **nothing** changes. If a
prompt moves between two identical runs, then every diff in the experiment is
unattributable and the whole matrix proves nothing — it looks like a result and
is noise.

Measured on `TASK-425`: the control earned its place twice over. It caught a
matrix that had compared **three different people** while reading PASSED, and
the first version of the control's own checker carried a silent fallback that
defaulted its question to "comparable" — the answer that lets a matrix pass.
**A control that fails open is not a control.**

### 0c. HISTORICAL PROVIDER ACTION AND CURRENT ELIGIBILITY ARE TWO CLAIMS — Zvonimir, 2026-09-28

**Report both, always, and never let one imply the other.**

    RIGHT   current qualification: rejected; historical sends: 18
    WRONG   not qualified, therefore never contacted
    WRONG   18 sends, therefore approved

A verdict recorded today says nothing about what was sent yesterday, and a
send that happened says nothing about whether it was ever licensed. The
TASK-430 audit is the live instance: 32 companies are now `rejected` in our
store and **18 of their contacts have already been emailed**, all in campaign
491. Both halves are true and the report carries both.

- **Business logic never depends on gitignored `work/`.** Safety logic,
  canonical schemas, claim-licensing evidence and any reproducible pipeline
  definition must be in git or unreachable from production — this is the same
  defect found twice already: `work/v2_run.py` (TASK-321, the production
  entrypoint had nowhere to terminate) and the case-study pages before
  TASK-365's rework (a gate whose only evidence lived in a gitignored
  directory fails open on a clean clone). Runtime and prospect state may live
  in `work/`; the logic that reasons about them may not.
- **Code governs; LLMs reason.** Suppression, sending eligibility, activation,
  budgets, ceilings, schemas, identity, provenance, provider state, cadence and
  approval are decided in Python. **No model verdict overrides a deterministic
  FAIL** (§28, model-routing §5).
- **One truth (§5).** Preview, XLSX, provider adapters, approval and QA are
  **projections** of one canonical plan, never second implementations. Do not
  create a parallel representation if one exists.
- **Consumer before producer (§4).** Wired means: *changing valid upstream
  information changes downstream production output through the real entrypoint.*
  A module, a function, a passing unit test, `A imports B`, or a doc saying
  "integrated" are **not** wiring. Zero production callers = **DISCONNECTED**.
- **Provider truth wins (§26).** Unreadable provider state is **UNKNOWN**, never
  clean/zero/safe. Complete pagination; a partial read is not estate truth.
- **Identity fails closed (§27).** ADMITTED / REFUSED / UNVERIFIABLE. Research
  stays account-bound; never bind Company B's research to Company A.
- **Provenance is never fabricated.** VERIFIED / CLIENT_APPROVED / INFERRED /
  UNKNOWN / **CLIENT_SUPPLIED**. INFERRED may inform strategy, never become a
  prospect-facing assertion. UNKNOWN is not invented.

  **CLIENT_SUPPLIED, sanctioned by operator decision, Zvonimir, 2026-09-27.**
  A fact from the client's own approved list — for Productive, the 09-07 CSV —
  enters the admitted pack as `CLIENT_SUPPLIED` and **records the source FILE
  and the source ROW**. Never a fabricated row: a record ingested before row
  capture reports `UNKNOWN`, which stays tellable from row `0`, and history is
  not rewritten.

      LICENSES        qualification and strategy. The ICP verdict, the segment
                      and the dossier a reviewer reads may all rest on it.
      DOES NOT        a prospect-facing claim, on its own, ever. A claim in
                      email or LinkedIn copy needs a public source or a stored
                      page. **The CSV alone is never a claim licence.**

  It joins INFERRED in the sentence above for claims, and the enforcement is
  structural rather than a string match: `packfacts.pack_for` returns the
  claim-licensing pack — identity-admitted research only — as `pack["facts"]`,
  and the client's own facts separately under `unused[CLIENT_SUPPLIED]`, so the
  list `copylint` and `sequencegate` license from and the list qualification
  reasons over are no longer the same list. Proof:
  `tests/test_a_client_csv_fact_cannot_license_a_claim.py`.
  **That closes the `copylint`/`sequencegate` path and only that path.**
  `src/claims.py` is a SECOND claim gate whose support model is every
  `company_facts` key and value, and a CSV figure still licenses a claim there:
  `ISSUE-048`, reproduced, open, and carrying the operator question it needs
  answered before it can be closed. Do not read this bullet as "the rule is
  fully enforced".
- **Grounding binds claim to evidence meaning (§28)**, not a token to the same
  token somewhere in the source.
- **Cadence is fixed.** Five emails, days 1/4/8/12/21, em1 new/A · em2 reply A ·
  em3 new/B · em4 reply B · em5 new/C — **pending §6 reconciliation**, which must
  document the canonical rule before anything changes.
  LinkedIn `PRODUCTIVE_LI_HEAVY_V1`, five steps, days 1/3/6/10/15, two branches
  (`docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`). Not simplified, not shortened.
- **GitHub is the source of truth.** Committed, pushed, remote SHA verified. A
  branch artifact is not on master.
- **Machine state wins over stale prose (§0).**
- **State is explicit, never inferred.** Never infer execution state from a proxy
  when direct evidence exists, and every operational state claim names its
  authority. Learned the hard way on 2026-09-27: a claim's recorded PID is the
  *claiming* process and not the worker, so a PID check reports every live claim
  as dead (which is why `--reap` refuses); a branch's task-file stage is an
  artifact and not task state, which hid 134 of 143 TODO tasks and starved the
  pool to zero ready while twelve workers polled; commit freshness is not worker
  liveness; a count of files in `TODO/` is not ready depth; a config block is not
  enforcement (`messaging_rules` was recorded and read by nothing); and a passing
  test is not runtime integration (`generate_campaign` had zero production
  callers while its tests were green). `TASK-424`'s lease-based registry is the
  scheduler instance of this invariant. Campaign, approval, provider, spend and
  provenance state are the next instances, after the one-account slice.

**GLM is a permanent independent reviewer**, not an implementer:
`docs/GLM-REVIEW-PROTOCOL.md` is the standing contract — review triggers,
checkpoints, the isolated-worktree rule, falsification over confirmation, and
the eight dispositions every finding must carry. Claude reproduces every
material finding independently before it becomes work.

## MODEL POLICY

`docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md` stands, sharpened by §15:
**use resetting capacity preferentially for useful eligible work; never create
work to consume capacity.** Allowance is a tie-breaker, not the objective.

    Qwen / local     implementation, bulk transformation
    Groq             trivial fast classification
    GLM Flash        extraction, synthesis, fact normalisation, relevance,
                     semantic QA, grounding, reply classification
    GLM high/max     strategy, ambiguity, difficult QA, independent critic
    Sonnet           prospect-facing copy — until §34's tournament says otherwise
    CODE             every safety decision

Escalation (§18): cheap pass with confidence → accept; uncertain or conflicting →
GLM high; **still ambiguous → operator question**, never a third model guessing.
Never max reasoning for trivial extraction. Router: `TASK-360`; observability:
`TASK-361`; no model slug outside `config/model_policy.yaml`.

## WORKER POLICY — KRITIČNI PUT IDE NA CLAUDE SUBAGENTE

**Operaterova odluka, 2026-09-27 popodne. Nadjačava starije pravilo "Qwen
implementira, Claude samo dispatcha i mergea" ZA KRITIČNI PUT.**

Razlog je izmjeren, ne pretpostavljen: Qwen je istoga dana pao na sva tri P0
pokušaja, svaki put tako da je izgledao gotov. TASK-400 je uhvatio `NotApproved` i
tiho se vratio na stari pipeline, pa je gate ostao otvoren; TASK-364 je izgradio
derivaciju naopako, iz već izgrađenih leadova, tako da mutacija plana ne može
promijeniti projekciju a testovi su zeleni po konstrukciji; TASK-372 je dobro
izmjerio pa predložio da se 228 padova prihvati kao nova baseline. Svaki krug je
kostao sate.

- **Kritični put implementiraju Claude subagenti (Opus)**, svaki u svom worktreeju,
  s jednom acceptance provjerom. Redoslijed: `TASK-426`, pa rework `TASK-364`, pa
  `TASK-400`, pa `TASK-425` (one-account dry run).
- **GLM ostaje neovisni verdikt**, uvijek protiv head SHA grane, nikada protiv
  mastera. Verdikt bez imenovanog SHA je NIŠTAVAN.
- **Claude mergea na GLM PASS.** Ako GLM ne odgovori u 45 minuta, Claude smije
  mergeati na temelju vlastite neovisne verifikacije PLUS pregleda drugog Claude
  subagenta. Dva neovisna pogleda, nikada jedan.
- **Qwen ostaje na punom kapacitetu izvan kritičnog puta**: taksonomija padova,
  auditi, backlog, testovi.
- **Stara pravila o štednji Claude tokena s prethodnog računa ne vrijede za
  kritični put.** Claude se troši tamo gdje skraćuje vrijeme do dry runa. Izvan
  kritičnog puta disciplina ostaje.

### KAD MERGEATI BEZ PITANJA, A KAD PITATI

**Operaterova odluka, 2026-10-01.** Dotad je svaka promjena gatea čekala
operatera, što je trošilo rundu po ispravku na nečemu što se može izmjeriti.

**MERGEAJ I JAVI, bez čekanja**, ako promjena zadovoljava SVE ovo:

    (a) samo POOŠTRAVA, ili ispravlja IZVOR AUTORITETA bez popuštanja
    (b) ima testove s negativnim kontrolama — ne samo pozitivne
    (c) GLM PASS na FINALNOM SHA, ne na nekom ranijem
    (d) produkcijsko mjerenje lažnih pozitiva, brojkom

Primjer koji je prošao sva četiri: `vertical: UNKNOWN` kao diskvalifikacija
prije plaćenog poziva — strože, besplatno, 6/6 izmjereno.

**PITAJ OPERATERA SAMO ZA:**

    popuštanje bilo čega što dolazi do prospekta
    provider writeove
    trošak iznad odobrenog limita
    kandidata izvan kanonskih pravila (npr. ručna persona)
    GO

Dvije stvari koje ovo pravilo NE mijenja. Prvo: **mjerenje lažnih pozitiva je
dio uvjeta, ne formalnost.** Promjena koja pooštrava a nije izmjerena nad
produkcijskim podacima nije kandidat za samostalan merge — "strože je" nije
mjerenje. Drugo: **ako promjena zadovolji (a)-(d) ali usput obrne nešto što je
operater izrijekom imenovao, to je popuštanje prema njemu i traži njegovu
riječ** — izmjereno 2026-10-01, kad je jedanaesta runda jednog gatea zatvorila
sve rupe i pritom počela odbijati formulaciju koju je operater propisao.

### COMMIT PORUKE NIKAD S BACKTICKOVIMA U `-m`

**Operaterova odluka, 2026-10-01, nakon osakaćene poruke isti dan.**

`git commit -m "... a \`continue\` in a gate is a pass ..."` prolazi kroz bash
**command substitution**: backtickovi se izvrše kao naredba i poruka se zapiše
BEZ njih. Izmjereno — "a `continue` in a gate is a pass" postalo je "a  in a
gate is a pass", a "Five `continue`s remain" postalo je "Five s remain".
Commit uspije, exit 0, ničim se ne javi da je tekst izgubljen.

- Poruke idu **preko datoteke** (`git commit -F <file>`) ili heredoca s
  navodnicima (`git commit -F - <<'EOF'`, s navodnicima oko EOF da se
  substitucija ugasi).
- **Nikad backtickovi u `-m`.** Ako moraš imenovati simbol u poruci, napiši ga
  bez backtickova.
- Poslije commita pročitaj poruku (`git log -1 --format='%B'`) i potvrdi da je
  cijela. Osakaćena poruka u povijesti je trajna dezinformacija, a uz
  `--amend` prije pusha popravak je besplatan.

### PRED-ENRICHMENT GATE: `vertical: UNKNOWN` JE DISKVALIFIKACIJA

**Operaterova odluka, 2026-10-01.** ICP gate propušta firme koje nisu agencije.
Izmjereno 6 od 6 na prvom plaćenom sourcing runu: prošli su **ženska
networking mreža**, **job board**, **časopis za oglašivače** i **adtech
proizvod za monetizaciju mobilnih igara** — svi na oznaci
`industry: "Advertising Services"` i svi s `vertical: UNKNOWN`.

WIBN je prošao jer se riječ "advertising" pojavljuje u njihovoj rečenici da je
networking **bolji** od oglašavanja. `vertical_why` je to i rekao: *"only 1
weak signal: not enough to classify"*. Sustav je znao; gate ga nije pitao.

- `segments.classify_vertical` se zove **PRIJE ijednog plaćenog poziva**.
  Besplatno je i razdvaja prave agencije od lažnih 6/6.
- `vertical: UNKNOWN` ili ne-agencijski vertical → **DISKVALIFIKACIJA**, bez
  trošenja kredita.
- Taj filter bi bio uštedio 30 od prvih 66 potrošenih kredita.
- Ramp task: `classify_vertical` kao formalni gate u pipelineu, plus mjerenje
  koliko od 37.763 "QUALIFIED" domena ima `vertical: UNKNOWN`. ICP gate je
  previše propustan i to je **ramp blocker**, ne canary.

### LEGACY KAMPANJE SE NE RESUMEAJU — NI IZ KODA NI RUČNO

**Operaterova odluka, 2026-10-01.**

Deset naših kampanja drži **1.555 redova u `sending_paused`**, a 491 se odbila
pročitati ("45 pages to walk") pa je njezin broj UNKNOWN i dolazi POVRH toga:

    503→473 · 504→431 · 505→409 · 492→122 · 494→50 · 493→40
    487→14 · 481→10 · 489→5 · 496→1          491 → UNKNOWN

**Resume bilo koje od njih odmah pušta stari copy** — bez CTA-a, s
odobrenjima koja više nisu valjana, i napisan prije nego su gateovi iz
2026-09-30/10-01 postojali. Resume 503/504/505 sam pušta 1.313 mailova.

TRI BARIJERE TRENUTNO STOJE, izmjereno 2026-10-01 na masteru:

    killswitch   odbija U KODU: `push.run(live=True)` diže iznimku, a
                 `tagsync.send` odbija bezuvjetno. Dva sloja, oba odbijaju.
    sending.live false za productive
    odobrenja    **0 od 3.005 je još valjano** — sva su postala stale kad je
                 odobrenje počelo vezati mailbox i potpis, bez grandfatheringa

Treća je najvažnija jer je jedina koja preživi upaljeni killswitch: čak i da
netko uključi slanje, nijedan od tih redova nema valjano odobrenje i svaki
traži ponovno odobravanje copyja kakav JEST, kroz gateove kakvi SU.

**Dispozicija se odlučuje nakon canaryja**, ne prije. Prijedlog, po kampanji:
stop/archive sve s nenultim `sending_paused`, uz razlog "stari copy bez CTA-a,
odobrenja nevaljana" — ali to je provider write i traži operaterov APPROVED.

### DVA TIPA KAMPANJA U SVAKOM WORKSPACEU — TRAJNO PRAVILO, Zvonimir, 2026-10-01

U EmailBison i u HeyReach workspaceu **uvijek** postoji mix:

- **(a) Resonate OS kampanje** — one koje je nas kod stvorio i **pozitivno zapisao
  u ledger**;
- **(b) interne Resonate kampanje** — vodi ih nas tim **rucno** za Productive.
  Nisu klijentove i nisu Resonate OS.

Operator je 2026-10-01 deklarirao kao **(b)**: EmailBison **274, 327, 328, 352**.
Poruka Bruni o vlasnistvu tih kampanja se **ne salje** — vlasnistvo je rijeseno.
Bruno je dalje potreban samo za re-contact politiku, DNC i cross-channel pravila.

**Za (b) vrijedi, bez iznimke:**

1. **NIKAD ih ne diraj.** Nikakav write: create, edit, pause, resume, stop,
   archive, delete, dodavanje ili micanje leadova, promjena sekvenci, mailboxa
   ili racuna — ni iz koda, ni iz agenta.
2. **Provider-write guard to odbija u kodu.** Default je **REFUSE** za svaku
   kampanju koja **nije pozitivno zapisana kao Resonate OS u ledgeru**. Odsustvo
   zapisa je odbijanje, nikad propusnica.
3. **Svatko tko je u njima je VEC KONTAKTIRAN** -> **NOT CLEAN** za canary; za
   ramp vrijedi re-contact pravilo nize.
4. **Uci iz njih, samo read-only.** Koje poruke, subjecti, angleovi, persone,
   verticali i geografije su dobili replyje — pozitivne i negativne; reply rate
   po kampanji i po koraku; timing. Rezultat: dokument s nalazima **bez PII** za
   copy i targeting. Svi negativni replyji, DNC-ovi, unsubscribeovi i bounceovi
   iz njih idu u **lokalni** suppression/touch ledger — nikad provider write.
   Learning traka **ne blokira canary**.
5. **Ownership klasifikator ima tri stanja:** `resonate_os` (u ledgeru),
   `resonate_internal` (operatorov popis u configu — provider nema owner polje,
   pa je popis jedini autoritet) i `unknown`. Kampanja koja nije ni u ledgeru ni
   na popisu je **UNKNOWN**, a UNKNOWN znaci **"ne diraj"** i **"clanovi NOT
   CLEAN"**. Nove interne kampanje operator dodaje u popis.
6. **Isto vrijedi za HeyReach kampanje**, istim trima stanjima.

487/489/493 i legacy Resonate OS kampanje (1.555 redova, nikad resume) ostaju
nedirljive po svojim vlastitim pravilima; ovo pravilo ih ne mijenja.

### LEAD KLASIFIKACIJA — TRAJNO PRAVILO, Zvonimir, 2026-10-01

**ZAMJENJUJE prethodno re-contact / COLD LEAD pravilo istog dana.** Implementira
se u `eligibility` i u collision putu. Svaki lead koji ulazi u Resonate OS prolazi
ovih pet koraka **po redu**, i ishodi su **međusobno isključivi**.

#### 1. TRAJNA BLOKADA

Bez obzira na izvor — Resonate OS, interne/rucne kampanje, HeyReach, rucni rad:
negativan reply, DNC, unsubscribe, opt-out reply, bounce/invalid, operator
exclusion, suppression lista -> **BLOCKED zauvijek**.

- **Status je autoritativan, ne replies brojac.** `replied` uz `replies: 0` je
  BLOCKED.
- **Aktivan razgovor ili pozitivan reply -> ide covjeku**, nikad u automatski
  outreach.

#### 2. ON HOLD

Lead je **trenutno u live kampanji na bilo kojem kanalu, bilo cijoj** — Resonate
OS ili interna/rucna: status `in_sequence`/`active`/`queued`/`pending`, **ILI**
pauzirana kampanja u kojoj lead ima **ne-terminalne** redove (resume bi ih
pustio). Tretira se kao kontaktiran i **ne dira se**; ponovno se evaluira kad
kampanja zavrsi.

**Legacy Resonate OS kampanje (1.555 redova iza pauze) drze svoje leadove ON HOLD
dok ih operator formalno ne zatvori.**

#### 3. JE LI GA KONTAKTIRAO RESONATE OS?

**Autoritet:** provider truth o slanjima ILI akcijama u kampanjama koje su
**pozitivno zapisane kao Resonate OS u ledgeru** (nas kod ih je stvorio), na oba
kanala. **Ne lokalni touch ledger sam po sebi** — on zna biti prazan.

- **a) DA -> STARI LEAD -> REVIVAL traka** (pravila u 5).
- **b) NE -> COLD LEAD -> potpuno nov pristup**, puna sekvenca, nov copy,
  **bez obzira** je li bio targetiran kroz interne/rucne kampanje ili rad ljudi.
  **Rucna povijest ga ne cini starim leadom.**
- **c) Ne moze se utvrditi** (lookup pao, nepotpuna paginacija, nejasan status)
  -> **UNKNOWN -> BLOCKED** dok se ne utvrdi. **UNKNOWN nikad ne postaje cold ni
  revival.**

#### 4. RAZMAK OD ZADNJEG KONTAKTA

COLD lead kojeg je **rucna ili interna** kampanja kontaktirala unutar zadnjih
**[N] dana** — zadnji prospect-facing touch s **bilo kojeg** izvora, iz provider
truth — **ceka da produ [N] dana**. `0` znaci bez razmaka.

`N` je **config vrijednost**, jedna izmjena, ne konstanta u kodu. Operatorov
predlozak je 14; produkcijska vrijednost je ono sto stoji u configu i doc koji
tvrdi drukcije je pogresan.

#### 5. REVIVAL PRAVILA — PREDLOZENO, ceka odobrenje

**Do operatorovog odobrenja revival leadovi se samo KLASIFICIRAJU, ne salju.**

- Minimalni razmak od zadnjeg **Resonate OS** toucha: **30 dana**.
- **Nov angle i nov copy** — ne ponavljati ono sto je vec poslano. Kraca
  sekvenca.
- Copy se **ne pretvara da je prvi kontakt** ako nije, i **ne prepisuje** stare
  poruke.

#### 6. INTERNE KAMPANJE

Nedirljive po vlastitom pravilu (vidi "DVA TIPA KAMPANJA"): samo se citaju i uci
se iz njih. Clanstvo u internoj kampanji **ne** cini lead starim leadom — ono ga
cini ON HOLD dok je kampanja ziva, i COLD kad nije, uz razmak iz tocke 4.

### U WORKTREEJU JE `git stash` ZABRANJEN

**Operaterova odluka, 2026-10-01, nakon incidenta iste noći.**

Git worktreejevi dijele **jedan jedini stash ref** za cijeli repozitorij. Stack
je globalan, worktree nije. Izmjereno 2026-09-30: jedan agent je u svom
worktreeju pokrenuo bare `git stash pop` i time izvukao **tuđi** nepospremljeni
rad — `src/personalization.py` (+379 linija) i untracked test (+131 linija) —
u svoj tree. Žrtvin worktree je tiho ostao čist i taj agent je bio na putu da
ponovi višesatni posao.

- **Agent NIKADA ne koristi `git stash` ni `git stash pop`.** Rad se odlaže
  **commitom na vlastitu granu** (WIP commit je dovoljan i poželjan).
- Ovo pravilo ide u brief **svakog** agenta koji dobiva worktree, ne samo kad
  se očekuje paralelni rad. Paralelni rad je norma.
- Ako se stash ipak mora koristiti: `git stash push -u -m "<jedinstvena-oznaka>"`,
  odmah zapiši SHA unosa (`git stash list --format='%H %gs'`), vraćaj s
  `git stash apply <sha>` — **nikad `pop`** — i unos briši tek nakon commita,
  pronalazeći ga po oznaci jer se pozicije pomiču.
- **Oporavak ako se dogodi:** rad nije izgubljen. `git stash list --format='%H %gs'`
  ga pokazuje, `git stash show --stat <sha>` daje tracked promjene, a
  `git show <sha>^3 --stat` untracked datoteke. Primijeni po SHA u worktree
  vlasnika i neka taj agent odmah commita.

## WORKER POLICY

**Standing order, 2026-09-26 evening:** the Qwen pool and GLM run at full capacity
on real backlog at all times; Claude only dispatches, verifies and merges. When a
worker finishes, the next task from the critical path or the standing backlog goes
out immediately; if the queue ever empties, post the reason in the status rather
than inventing work. Report per-worker task and Claude usage in every status.

**Standing order, 2026-09-26/27 overnight — the 12-ready-task floor.** Found the
hard way: the pool went fully idle for a stretch because nothing refills TODO/
while Claude is doing something else, and a sweep only ever dispatches a task
file that already exists. **Claude never ends a turn, or goes idle waiting on
something, while fewer than 12 task files sit ready in `docs/qwen-tasks/TODO/`.**
Refilling the queue with real, falsifiable, acceptance-checked tasks from the
standing backlog comes BEFORE waiting for anything else to finish. A 15-minute
`ResonatePoolSweep` scheduled task runs `scripts/pool.sh sweep` regardless of
whether Claude is active, precisely so the pool does not depend on Claude's
attention to keep moving.

**SUPERSEDES `docs/OPERATOR-DIRECTIVES-2026-09-25.md` §13 entirely.** That section
required 100% utilisation and 2–3 queued tasks per worker, and called an idle
worker a defect.

**§1 replaces it: MAXIMIZE CRITICAL-PATH THROUGHPUT, NOT WORKER UTILIZATION.**

- **An idle worker is not a defect. A shallow queue is not a defect.** Neither is
  reported as one.
- **Do not invent, split or prematurely execute work to keep workers busy.**
- Parallelise only work that is *all four*: independent, useful, non-conflicting,
  and verifiable/integrable without blocking the critical path.
- Claude orchestrates and merges. Qwen implements. GLM reviews first-pass.
- Buggie (§21) is scaled to consequence: full review for safety/provider/approval/
  suppression/provenance/ledger/critical integration and at master checkpoints;
  targeted checks otherwise. **Report-only. Findings become tasks. Buggie does not
  fix its own findings.**

## DEFINITION OF DONE

§36. Not done because code was written, the worker exited 0, tests were claimed, or
a branch was pushed. Critical-path tasks report: TASK · STATUS · FILES · **SCOPE
DEVIATIONS** · TESTS · TEST RESULTS · **PRODUCTION ENTRYPOINT** · **CONSUMER** ·
**END-TO-END EFFECT** · LOCAL SHA · REMOTE SHA · BRANCH · MERGED? · MASTER SHA
AFTER MERGE · PRODUCTION IMPACT · REMAINING RISK.

**Claude verifies before merge. Cherry-pick only the required files** where a
branch carries junk or scope drift — merging pollution to save time is forbidden,
and one such branch would have silently reverted the provenance fix.

Tests must be falsifiable (§20): ask *how could this pass while the implementation
is still wrong?* Not accepted: proving a function exists, JSON shape, a token
appearing, a fake cassette returning fake data.

**Suite (§19):** baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, **128
named failures**. A known baseline failure is visible debt; a **new failure
BLOCKS**; the baseline count **may never silently increase**. Never delete a
legitimate test for green CI — a safety test failing because production violates
the contract is evidence.

## LAUNCH BLOCKERS

Open, and each blocks prospect-facing launch:

1. **Approval hash not enforced** — `require(campaign_id)` passes no hash at all
   three call sites, so an approval survives a re-render. §22, `TASK-328`.
2. **Resume does not re-evaluate suppression** — `EMAIL_RESUME` is `facing=False`,
   so `revalidate()` never runs. §23, `TASK-331`.
3. **No mailbox has a stored signature** — 155 email steps render empty. §24,
   `TASK-341`. Must become a Launch Readiness item.
4. **Cross-channel stop unproven at the provider** — readback required, never
   inferred from logs or mocks. §25. Needs separate operator authorisation.
5. ~~**Grounding passes on token coincidence**~~ — **CLOSED 2026-09-27**,
   `TASK-330` integrated from `qwen-worker-4-r61` at `82b828c2b779`.
   `copylint._traces` no longer reduces to "the token appears anywhere in the
   pack": a specific now traces only when the pack SENTENCE containing it shares
   at least two non-stopword content words with the draft sentence, so
   "raised 50M in 2019" can no longer launder "grew revenue by 50M last
   quarter". Production chain proved rather than asserted: `copylint.untraceable`
   is called by `copylint.report` AND by `sequencegate.check`, and `sequencegate`
   is imported by `bisonfactory` and `generate_campaign`.
6. **`unrendered_variable`** — 13 of the fifty's 31 written leads. §37 step 15.
7. **Preview duplicates cadence** — hardcoded LinkedIn days 1/3/8/14 against a
   canonical 1/3/6/10/15. §5, §37 step 18, `TASK-343`.
8. **All 6 offers are `approval_status: pending`** — correct fail-closed, and an
   **operator decision** (§40). Campaign strategy has no approved offer to use.

Launch Readiness (§35) reports PASS / WARNING / BLOCKED / UNKNOWN per category.
**UNKNOWN is not PASS.**

### TWO THINGS TASK-426 MADE VISIBLE, 2026-09-27 — not new defects

`TASK-426` is merged (master `6e72f9f0`), so `bisonfactory.stage()` works for the
first time since 2026-09-26 and gates downstream of it became REACHABLE. Two
pre-existing problems surfaced the moment they could run. Neither was created by
the fix, and neither is to be "fixed" by relaxing anything.

9. **60 of 64 stored productive campaigns are unstageable — and the cause is
   STALE STORED ROWS, not a broken cadence.** They refuse one gate earlier than
   the sequence gate, at `_require_declared_cadence`. **This does NOT block
   `TASK-425`,** and an earlier version of this entry said it did. Measured
   directly rather than inferred from the refusal message:

       a NEW productive campaign's cadence   em1..em5 AND li1..li5  ← canonical
       stored cadence_steps, 64 rows:  48 none stored · 12 ('em1','em2','em3')
                                        3 em1..em5 · 1 ('em1',)

   `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1` declares five email steps on days
   1/4/8/12/21 and five LinkedIn steps on 1/3/6/10/15 — exactly the canonical
   rule above — and `cadence.steps_for(None, config)` returns all ten for
   productive. So the config and the library AGREE and are correct; what is
   wrong is history. The 48 rows storing nothing are refused BY DESIGN
   ("DECLARED, NOT INHERITED": the fallback through the client config is what
   once let a live campaign be staged against a cadence it never chose), and 13
   rows carry a declaration made before the cadence had five steps.

   **So the §6 reconciliation is not "which cadence is canonical" — that is
   settled at five. It is "what happens to 13 stale stored declarations":
   migrate them, or leave them refused.** Do not change the cadence, and do not
   invent a fourth one. `TASK-425` builds its own campaign and gets em1..em5.
10. **786 sendable contacts belong to companies that were never ICP-qualified.**
    Once item 9 is resolved, the now-working gate will refuse re-staging of NINE
    staged campaigns — 491, 492, 493, 494, 495, 496, 497, 498, 500 — because
    every one of their records is `not_processed`, i.e. carries no ICP verdict at
    all. **That is the CORRECT fail-closed answer** under "Company first: no
    paid person-level call before a company reaches an explicit ICP verdict".
    It is recorded here because 491-498 have already SENT, so this is a real
    pre-existing problem the gate uncovered rather than an obstacle it invented.

**A dry run does not run the sequence gate.** THIS one does block TASK-425 criterion 3. `stage()` returns before both
`_refuse_copylint` and `_refuse_sequence_gate` when `live=False`. Pre-existing.
It directly blocks `TASK-425` acceptance criterion 3, which requires sequencing
"enforced by `sequencegate`, with a negative test" from a run that performs zero
provider writes.

## DEFERRED WORK

`docs/BACKLOG.md`, with a rationale per entry. Per §31: conversational onboarding
and its UI, large onboarding workflow, autonomous account orchestration, the
50–100 account model bench, elaborate multi-provider usage automation, new external
signal sources, Reddit, Google Reviews, major learning automation, retargeting
automation, UI polish.

Also deferred by covering instruction: **`TASK-359`** (nightly multi-provider usage
job) until the internal ledger is proven — only the ledger-based cost view runs,
and **no scheduled task is registered**; **`TASK-363`** (copy tournament) until the
50-account slice is stable (§34).

## TIME TO LIVE — NACIN RADA, Zvonimir, 2026-10-01

### STO "LIVE" ZNACI — MINIMUM, NE SAVRSENSTVO

1. **E1 / L1** kao dosad: jedan canary po kanalu, s operatorovim GO-om. Email GO
   i LinkedIn GO su **dva odvojena GO-a**.
2. Zatim **ATTENDED BATCH MODE**: batch od **5-10 firmi**. Sustav radi
   kvalifikaciju, verifikaciju, collision i re-contact pravilo, copy, gateove i
   projekciju; operator daje **JEDAN GO po batchu** nakon sto procita sazetak i
   uzorak copyja.
3. **Durable controller, Hetzner i potpuni ramp NISU preduvjet** za attended
   batcheve. Preduvjeti su tocno ovih pet:
   - **re-contact pravilo** + **provider-backed provjera po osobi**;
   - **guard za interne kampanje** (default REFUSE izvan ledgera);
   - **cross-channel stop** za kanale koji se koriste;
   - **provider readback nakon svakog batcha**;
   - **nula duplikata**: idempotency po **osobi i kampanji**, provjerena
     **prije** slanja, ne nakon.
4. **Autonomni ramp do 50 dolazi poslije**, kao zasebna faza. Ne mijesa se u
   attended batcheve i ne odgađa ih.

### ROKOVI

| Milestone | Rok |
|---|---|
| Email canary checkpoint | **danas** |
| LinkedIn canary checkpoint | **sutra do 12:00** |
| Prvi attended email batch (5 firmi), spreman za GO | **2 radna dana nakon E1** |
| Prvi attended LinkedIn batch | **2 radna dana nakon L1** |

Rok koji nije realan javlja se **odmah**, s razlogom — ne na dan roka.

### LIMIT PERFEKCIONIZMA — najvise 3 GLM runde

Po jednom gateu ili jednom ispravku: **najvise tri GLM runde**. Ako nakon tri
runde i dalje postoji rezidual, **mergea se najjaca verzija koja je strogo bolja
od mastera**, rezidual se dokumentira kao **poznat** i zatvara paralelno.

**Iznimka, i ona se ne prelazi:** rezidual koji moze dovesti do
**slanja krivoj osobi**, **duplikata**, ili **lazne tvrdnje koju operator u
checkpointu ne bi mogao uociti**. Tada se **stane i javi**, bez mergea.

### TRAKA: ONBOARDING DRUGOG KLIJENTA — paralelno, ne dira canary

- Izmjeriti **koliko je sustav stvarno multi-client**: sve sto je hardkodirano na
  Productive — config, offeri, Second Brain, ICP, verifikacijska politika,
  potpis, CTA, kampanje, Slack, ledger, interne kampanje. Rezultat je lista
  **`file:linija` -> sto treba parametrizirati**.
- Napraviti **predlozak** `config/clients/<novi>.yaml` + offers + Second Brain
  strukturu + **checklistu onboardinga**: koje inpute trazimo od klijenta — ICP,
  persone, offeri, dopustene tvrdnje, CTA, sender identitet, mailboxi, LinkedIn
  racun, DNC lista, interne kampanje, re-contact politika.
- Cilj: kad podaci dodu, onboarding traje **dane, ne tjedne**. Ime klijenta
  dolazi naknadno; do tada se radi genericki.

### SLACK STATUS

Svakih 90 min u `#resonate-os`: EMAIL, LINKEDIN, WORKERS, RAMP, **MULTI-CLIENT**,
OPERATOR odluke, i **svaki rok koji kasni** — imenovan, s razlogom.

## CURRENT MASTER SHA

Last verified: **`6e72f9f0`** on `origin/master`, 2026-09-27 21:05 Europe/Zagreb,
by `git rev-parse master origin/master` (both matched). It moved four times in
two hours this evening — `1f4d464c` → decisions and the killswitch proof →
`4bff3a7a` (16 integrated results) → `6e72f9f0` (TASK-426). The values before
that (`3badeab0`, and the afternoon handoff's `50b55c92`) were both stale when
read. **Assume this line is stale.**

This line is a snapshot and goes stale by design. **Derive it, never trust it:**

```bash
git fetch origin && git rev-parse master origin/master
```

§30 requires a machine-derived status command so state stops living in prose. Until
it exists, `scripts/task_registry.py` and `scripts/claim_task.py --status` are the
authorities for task and worker state, and the provider is the authority for
campaign state.
