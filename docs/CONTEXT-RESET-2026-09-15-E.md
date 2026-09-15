# Context reset checkpoint E, 2026-09-15

Supersedes `CONTEXT-RESET-2026-09-15-D.md` where they disagree. Everything here
was read from git, from a provider, or from a live process in this session.
Nothing is inferred from a plan.

**THE TWO LINES THAT MATTER MOST:**

    The sequence was NEVER the copy. 599020 holds pure merge variables and the
    words arrive per lead in customUserFields.

    ONE THING BLOCKS THE FIRST LIVE COHORT: four seals in TASK-137.

---

## 1. CURRENT MASTER

    master HEAD     14354e3   (git log --oneline -1 is the authority)
    origin/master   identical, verified this session
    worktree        clean

**All worker branches with work are pushed.** One exception, handled:
`qwen-worker-r9` was rejected non-fast-forward and is preserved as
**`qwen-worker-r9-preserved`** (`01b29a7`, TASK-119 provider-id normalisation,
unreviewed).

Worktrees `resonate-qwen-worker` and `-2`..`-8` exist. No qwen workers running
at reset (node procs 0). One python process was still finishing an enrichment
batch.

## 2. PRODUCTION STATE - INTERNAL vs PROVIDER-CONFIRMED

### PROVIDER-CONFIRMED (read from HeyReach this session)

    campaign 599020   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
                      DRAFT, startedAt NULL, created 2026-09-13
                      LEADS: 0
                      list 933603 attached, 0 items
                      sender 174892 attached, active
                      sequence 24 nodes, readback 27/27 PASS
                      sequence_hash 32f8dde79bfa0f27
    account           83 campaigns; exactly ONE created by Resonate OS
    senders           41 seats, 33 healthy, 1 active-but-authIsValid-FALSE,
                      7 inactive. ~1054 connection requests/day ceiling.
                      ZERO healthy seats are uncommitted.

    EmailBison        481 paused, 23 leads, 0 sent
                      451 completed, 1 sent
                      Both ours. Nothing new created.

**NO Resonate OS campaign is live or sending. Zero touches have been sent this
session. Zero leads exist at any provider.**

### INTERNAL (work/queue.jsonl - gitignored, NOT in git)

    queue             550 records (was 300), 550 unique domains
    not dropped       431
    dropped           119  - ICP qualification refusing them, which is the gate
                             working. Dropped accounts correctly skipped the
                             PAID person-search: "no ICP verdict (rejected),
                             skipped decision-makers"
    contacts          151  (was 92)
      LinkedIn URL    151  (100%)
      email           139
      sendable         61
    CLEAN FOR FIRST TOUCH   122   (151 minus 29 carrying a prior
                                   bison_lead_id, held out of campaign 1)
    states            queued 331, dropped 119, drafted 44, held 34,
                      verified 19, approved 3

**122 is the production-ready cohort** and was accurate at reset.

### Enrichment

Two batches, both inside their caps:

    batch 1   40 records, 74 of cap 80 credits, 59 new contacts
    batch 2   80 records, cap 160

Cost model from its own dry run: ~1.3 credits/record. **Always use `--cap`.**
A first attempt run in the foreground was killed at a 10-minute limit having
committed nothing - run enrichment in the BACKGROUND.

## 3. THE IMMEDIATE P0 BLOCKER - TASK-137

`docs/qwen-tasks/TODO/TASK-137-narrow-four-seals-then-ship-the-control-arm.md`

Everything for the first live cohort is established EXCEPT this.

### What is already true - DO NOT REDO

    cohort        122 LinkedIn-reachable, no prior outreach
    sequence      ALREADY CORRECT. 599020 holds PURE MERGE VARIABLES -
                  {connection_note}, {connected_1..4}, {message_2..4}.
                  The words arrive PER LEAD in customUserFields.
                  **NO SEQUENCE WRITE IS NEEDED.** This is the single most
                  important architectural fact in this document; three days of
                  copy work were spent on copy that was never in the campaign.
    copy          the operator's hand-written fallbacks, approved as CONTROL
    lead builder  build_lead_pairs already accepts arbitrary custom fields
    connection    sequence root is CHECK_IS_CONNECTION - the provider branches
                  at runtime, so a connection request NEVER reaches an existing
                  connection. This requirement is already satisfied.
    predicate     heyreach.campaign_cannot_send - fail-closed, DRAFT ONLY,
                  called in heyreachfactory.ensure_leads immediately BEFORE the
                  write. 20 tests, proven non-inert.
    readback      VERIFIED live on campaign 565765: 1000 leads paged, each with
                  leadCampaignStatus, leadConnectionStatus, leadMessageStatus,
                  errorCode, leadCampaignStatusMessage.

### The permission that is intended - DO NOT REINTERPRET THIS

`LINKEDIN_ADD_LEAD` must NOT become globally or unconditionally supported.

    only a Resonate-created campaign
    campaign must be DRAFT / proven unable to send
    provider state RE-READ immediately before the write
    REFUSE if the campaign can send        (IN_PROGRESS, PAUSED, FINISHED)
    REFUSE if the state read fails or the status is unknown
    counterfactual tests proving rejection must be preserved
    the four seals are NARROWED DELIBERATELY, never deleted
    LINKEDIN_ACTIVATE remains separately sealed and needs its own decision

PAUSED is excluded because a human can resume it. FINISHED is excluded because
"finished" describes the leads already in the campaign and says nothing about
one added afterwards. Both exclusions are pinned by tests.

### The four failing seals

`tests/test_a_person_can_enter_a_heyreach_campaign.py`, class `TheSealStillHolds`:

    test_linkedin_add_lead_is_not_supported
    test_supported_is_exactly_this
    test_the_add_lead_operation_is_still_not_supported
    test_the_write_layer_still_refuses_prospect_facing_ops

**Claude enabled the route, saw these four fail, and REVERTED.** Master is
clean and the seals hold. Do not narrow them casually - keep
`test_supported_is_exactly_this` as an exact-tuple assertion so any future
addition stays deliberate; update the expected tuple rather than loosening the
check.

## 4. COPY AND RESEARCH STATE

### Three human reads, three NOs, and the pattern IS the finding

TASK-098, TASK-130 and TASK-136 all returned **DOES NOT BEAT FALLBACKS**. The
four TASK-130 defects are genuinely gone, measured on 12 records / 73 steps:

    easy out present in li6    11 of 69  ->  100%
    referral ask in li6                  ->  100%
    "I noticed"                34 emails ->    0%
    "i admire how"             ~16%      ->    2%
    same greeting six times    69 of 69  ->    0

**But each fix traded a named defect for a new sameness.** TASK-136: all 12
sequences walk one six-beat arc - intro, question, problem, product, another
angle, templated close - and *"the fallbacks avoid this because each has a
different shape."* Variants vary the WORDS INSIDE a step; nothing varies the
SHAPE of the sequence. Phrase-level fixing cannot reach a bar set by shape.

**li6 templating**: pairwise similarity median 0.62, max 0.94, 6 of 36 pairs
above 0.8. NON-BLOCKING unless recipient-visible duplication makes it material -
two contacts at one company receiving the same close is the case that matters.

**The fallbacks are the validated CONTROL** (client config): `connection_note`,
`connected_1..4`, 83-115 chars each, four different shapes, no claim about the
recipient.

### research[] - and a correction to an earlier audit

**`docs/CRAWLER-AUDIT-2026-09-15.md` Part 1 is WRONG and Part 3 corrects it.**
Claude claimed the prompt could not see crawled evidence. It always could:
`generate.py:490` passes `public_evidence` from `research.for_prompt(rec)`,
which reads `rec["research"]` and supplies `field`, `source_url`,
`retrieved_at`, `fact`. **The model was never blind.**

    research rows                    695 across 203 of 300 records
      provider apify                 625
      provider local_http (webfetch)  70
    navigation/junk rows             237 of 695  (34%)
    records whose FIRST THREE are junk  47 of 203

`for_prompt` takes `[:3]` in stored order with no quality ordering, so those 47
records are shown menu fragments. TASK-135's quality-filtering change is
integrated. It moved NO claims-gate outcome (26 drafts, 13 records, zero
unsupported-claim rejections in either arm) and still makes 47 records show
facts instead of page furniture.

**Crawler provenance**: `src/webfetch.py`, free, stdlib only, runs as the free
leg before the paid Apify crawl. Real crawls of real pages - `/` 202, `/about`
91, `/about-us` 29, `/team` 22.

**TTL GAP**: `research.why()` opens `if existing_evidence(rec): return None`.
**Once a record has any evidence, research never runs again.** No TTL, no
staleness comparison. `age_days`, `published_at` and `confidence` are NULL on
all 695 rows. Newest evidence is 3 days old, oldest 8. Tolerable for
positioning; NOT tolerable for hiring signals or recent announcements.

## 5. THROUGHPUT - THE 30K ESTATE

**The "30k domains" file is a PEOPLE file**, 52 columns, every row carrying a
business email:

    rows                     51,741
    UNIQUE DOMAINS           20,944   at 2.5 contacts/domain, max 57
    already queued                9
    NEW accounts available   20,935
    US / UK / CA             27,293 / 8,594 / 5,413

The estate was never inventory-limited. 300 of 20,944 domains had been
ingested - 1.4%.

`scripts/build_intake_batch.py` adapts it: `Organization` -> company, domain
from `Email_Business`, collapsing people into ACCOUNTS. One record is a
COMPANY; the source is one row per PERSON. **Never create one record per
person** - that is the shape the cohort policy forbids.

    py -3 scripts/build_intake_batch.py --limit 250 --country "United States"
    py -3 -m src.ingest batches/productive-intake-00000-00250.csv \
        --client productive --lane domains

Batch files are `batches/productive-*.csv` and are GITIGNORED - 20,944 real
companies somebody paid for.

**Nothing in that file is verified.** A populated `Email_Business` means
somebody sold us a string. Contacts are discovered and verified later.

Pipeline: domain -> dedupe -> structured data -> cached/source-backed research
-> crawler when required -> ICP qualification -> contact enrichment ->
historical lead/connection state -> cohort -> campaign -> provider readback ->
outcomes -> learning -> next batch. **Do not wait for all 30k before shipping.**

## 6. HISTORICAL STATE - STILL REQUIRED

Use old leads, previous outreach, previous replies, existing LinkedIn
connections and previous positive/negative outcomes when deciding channel,
action and message. 29 of the 151 contacts carry a `bison_lead_id` and are held
out of campaign 1 for that reason.

**Do not treat a contact with history as a cold prospect.**

## 7. ORCHESTRATION POLICY - PRESERVED

`docs/ORCHESTRATION.md` section 0 is the rule: **Claude does not idle because a
worker is running.** When review, integration and orchestration queues are
empty, Claude takes the highest-value independent execution task. Do NOT
manufacture tasks for utilisation - there is more real work than capacity.

Atomic claiming via `scripts/claim_task.py` (`O_CREAT|O_EXCL`, proven: 8
racers, 1 winner). `--reap` is DISABLED - the recorded pid belongs to the
claiming process and a pid check would free every live claim. Worktree locks
via `mkdir` prevent two agents in one directory.

Safe live production is P0. Non-blocking perfection work must not postpone
deployment. Never weaken safety, claims or provider-state gates to ship.

## 8. DURABILITY POLICY - PRESERVED

review -> test -> commit -> push -> **verify remote**. Not at session end.
Never commit secrets, credentials, raw lead data or runtime datasets.
`work/` is gitignored and is the production ledger - **git is not the
database.** Runtime state lives in `work/queue.jsonl` on this machine.

## 9. CLIENT #2 READINESS

Known Productive-specific assumptions, recorded and NOT refactored (they do not
block production): the client config carries the fallback copy inline;
`scripts/build_intake_batch.py` hardcodes the Productive source CSV path;
several task scripts name `--client productive` by default. Do not refactor
these now.

## 10. ORDERED FIRST ACTIONS FOR THE FRESH SESSION

    1. Read this file, CLAUDE.md, QWEN.md, docs/ORCHESTRATION.md.
    2. VERIFY rather than reconstruct:
         git log --oneline -1
         git rev-parse master origin/master
         py -3 scripts/provider_truth.py
         py -3 scripts/task_registry.py
    3. Inspect TASK-137 status - it may be running or done on a worker branch:
         py -3 scripts/claim_task.py --status
         git for-each-ref --format='%(refname:short)' refs/heads/ | grep qwen
    4. Finish/review/test the NARROW LINKEDIN_ADD_LEAD permission per section 3.
       Run the seals OFF THE PROCESS, never through a pipe:
         py -3 -m unittest tests.test_a_person_can_enter_a_heyreach_campaign
         py -3 -m unittest tests.test_the_heyreach_write_contract
         py -3 -m unittest tests.test_campaign_cannot_send
    5. Commit, push, verify remote.
    6. Re-read provider campaign state (599020 must still be DRAFT, 0 leads).
    7. Deploy the 122-lead cohort to 599020 with FALLBACK copy in
       customUserFields. Multiple healthy senders where appropriate.
    8. Provider readback - verify actual lead count, status and per-lead
       errorCode. **A local success message is not a lead.**
    9. Activation as a SEPARATE gated step. LINKEDIN_ACTIVATE is still sealed.
   10. In parallel: continue 30k intake, enrichment (capped, background),
       historical inventory, and learning.

## 11. DO NOT REPEAT - ALREADY SETTLED

- **The crawler exists, works, and its output reaches the prompt.** Settled in
  the audit Part 3. Do not re-investigate whether the model sees evidence.
- **The sequence is already correct.** Merge variables, 27/27 readback. Do not
  rewrite it.
- **HeyReach carries multiple messages per node** - 67 of 83 campaigns do, up
  to 20. Variants do not need separate campaigns. Settled by TASK-121.
- **Approval binds to exact content.** `approval.is_approved` compares the
  stored fingerprint to current content; regenerated copy cannot inherit a
  verdict. Proven by mutation.
- **The four em_dash leads are blocked by the quality gates, not a bug.** The
  model makes three attempts, all fail repetition/lint, nothing is stored.
  377 of ~440 rejections are repetition. Enrichment question, not engineering.
- **Approval-history loss is FIXED** in `generate.store_step`. 72 historical
  records are recoverable from a backup; restoration is queued as an audit
  migration in `docs/state/audit-recovery/`, NOT a production blocker.
- Do not quote 8.49%. Do not quote any open rate - `open_tracking` is False
  estate-wide. Do not count an UNKNOWN reply as negative.

## 12. UNRESOLVED UNCERTAINTIES

- Whether a challenger arm can ever beat the fallbacks by phrase-level fixes.
  The evidence says shape, not words, is the constraint.
- Whether `excludeInOtherCampaigns` can be set on 599020 - all three exclusion
  flags are False and no update route is established. Our 151 contacts may
  overlap the client's 83 existing campaigns; the 122-lead cohort avoids this
  only via our own `bison_lead_id` history, not via provider-side exclusion.
- The response body of `AddLeadsToCampaignV2` is still unknown. The readback is
  the proof mechanism and is verified.
- Whether the auth-invalid seat 129531 - live on campaign 523987 with 33,710
  leads - is recoverable. It is the client's own campaign, out of scope, and
  the operator has been told.

## 13. RUNNING WORK AT RESET

No Qwen workers running. One python process finishing an enrichment batch;
`store.transaction()` commits per record so a kill costs only the record in
flight. Re-run enrichment with `--cap` in the background.

TASK-137 is in TODO and unclaimed. Two tasks READY. To restart the pool:

    export POOL_LOGS=/tmp/pool; export POOL_ROUND=r18
    bash scripts/pool.sh sweep
