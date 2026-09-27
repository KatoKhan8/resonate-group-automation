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
   `ISSUE-048` in `docs/state/PROBLEM-REGISTER.md`. **ANSWERED — see decision
   B immediately below. The sentence above is kept because it records what the
   code did, and the reproduction is the thing the fix is measured against.**

### DECISION B — 2026-09-28, Zvonimir. ISSUE-048 answered, TEMPORARILY AND BLUNTLY

**Operator decision, 2026-09-28, as the IMMEDIATE, TEMPORARY, CONSERVATIVE fix
to `ISSUE-048`. It closes the question decision 7 left open, and that question
is no longer to be asked.**

> The six CLIENT_SUPPLIED company fields may continue to be used for
> qualification, segmentation, prioritisation, strategy, offer selection and
> internal reasoning. They MUST NOT license a prospect-facing factual claim
> through EITHER claim-validation path. If the only evidence for a claim is one
> of those CLIENT_SUPPLIED fields, **fail closed and refuse the claim.** Do not
> weaken either validator to make the one-account test pass.

**IN FORCE ON BOTH PATHS as of 2026-09-28.** `claims.support_text` now skips
`packfacts.INGEST_FACT_KEYS`, and the key list is TAKEN from `packfacts` rather
than retyped, so the two gates cannot drift and a key added to
`ingest.INGEST_TO_FACTS` becomes unlicensed in both with no further edit.
Nothing is deleted from any record and nothing else is narrowed. Proof through
real entrypoints, provider writes 0:
`tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py` —
refused through `eligibility.decide` (the `push.py` path) AND through
`bisonfactory.stage`; refused IDENTICALLY with the client's value removed;
still decisive for `icp.score`, `segments.classify`, `qualify.company` and
`qualify.dossier`; and a control in which the same figure on the account's own
page reaches `eligible` and stages one lead, so the gate cannot be confused
with one that refuses everything.

**IT IS DELIBERATELY BLUNT, AND THE COST IS REAL AND MEASURED.**
`company_facts` carries no per-key provenance, so a value typed into the
client's spreadsheet and the same value returned by a provider are
indistinguishable once stored. B therefore refuses MORE than strictly
necessary. Two of the six keys are also written by real providers:

    headcount    headcount.observe() - the ContactOut free people-count and
                 blitz.company, resolved into company_facts["headcount"]
    industry     enrich's merge of contactout.company_info(domain), which
                 returns an `industry` of its own

The other four — `headline`, `employee_range`, `headcount_growth_12m`,
`products` — have no non-ingest writer into `company_facts`, so for those four
B costs nothing. Measured instance of what it does cost: with
`company_facts["industry"] = "Delivery Services"`, a value ContactOut
legitimately returns, the sentence *"You manage delivery for the studio."* was
clean before B and is refused under it — and stays clean when the same term is
on a page of the account's own domain. **That is the accepted cost of erring
toward refusal.**

**TEMPORARY. The real fix is fact-level provenance — `TASK-462` — and it is
REQUIRED POST-SLICE WORK, not to be built during the slice.** It is recorded
here and in `ISSUE-048` rather than as a file in `docs/qwen-tasks/TODO/`,
because a TODO file is claimable by any worker and this one changes licensed
claims. **Nobody may read B as the final data architecture.**
8. **The 13 stale stored cadence rows stay REFUSED. No migration.** New
   campaigns get the canonical five-plus-five. See item 9 under LAUNCH BLOCKERS
   for the measurement; the §6 reconciliation question is hereby answered and
   closed.
9. **The 786 contacts in 491-500 with no ICP verdict: classify their companies
   now** — read-only, Qwen or Groq, cost reported from the ledger, verdicts
   recorded, **the live campaigns untouched** — and report how many would not
   have qualified. `TASK-430`. **The decision about those nine campaigns goes to
   the operator afterwards and is not taken by whoever runs the classifier.**

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
  `src/claims.py` was a SECOND claim gate whose support model was every
  `company_facts` key and value, so a CSV figure still licensed a claim there:
  `ISSUE-048`. **ANSWERED AND CLOSED on 2026-09-28 by operator decision B** —
  `support_text` skips `packfacts.INGEST_FACT_KEYS`, so both gates now license
  from the same narrower list. The rule is enforced on both paths. B is
  deliberately blunter than correct and is TEMPORARY; read the DECISION B
  section above for what it over-refuses and why, and `TASK-462` for the real
  fix.
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
