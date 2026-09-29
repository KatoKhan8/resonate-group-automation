PRIORITY: READ FIRST

# HANDOFF — 2026-09-29 — RACHELE / 2020 COMPANIES

**Supersedes `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`.**
Written at 97% context to preserve exact state. **A fresh session should NOT
perform a broad architecture audit — follow section J.**

    master          6190f846
    origin/master   6190f846      (identical, verified by fetch)

---

## A. PRODUCTION SAFETY

Production is **Hetzner**.

    sending.live              false
    provider writes           0
    enrolments                0
    prospect-facing sends     0
    work/queue.jsonl          dd984f8a...caee2   UNCHANGED
    work/campaigns.jsonl      00b6f103...c5931   UNCHANGED
    Brand IQ                  untouched

**Say "nothing sent by this work". NEVER say "nothing was ever sent"** — the
provider is the authority for historical sends and the local ledger is
incomplete (912 provider sends against 1 recorded touch).

**TASK-564 and TASK-565 remain hard gates before any future live canary.**

---

## B. TASK-913 — THE 5+5 CONTRACT WORKS, AND IS **NOT MERGED**

    branch   origin/qwen-worker-3-r22   head 2fb19318   NOT MERGED

The writer contract is **proven capable** of `em1`-`em5` and `li1`-`li5`, all
non-empty, and **copylint has PASSED on a real Rachele generation**
(attempt 3, `off=[]`, `hold_kind None`).

Canonical LinkedIn authority is now **one** tuple:

    cadencelibrary.LINKEDIN_WRITER_KEYS = ("li1","li2","li3","li4","li5")

The old four-element cap and the legacy `("connect","msg1","msg2","msg3")`
authorities in `sequenceplan.py` and `generate.py` were removed on that branch.

**Measured successful chain, isolated zero-write validation:**

    WRITER        5 emails, 5 LinkedIn, all non-empty
    SEQUENCEPLAN  em1..em5, li1..li5, ps_em1, ps_em3
    BISON         1 lead, 5 email steps
    HEYREACH      1 lead, li1..li5
    approval hash dc8018c8d222f0a8

**Root causes TASK-913 fixed** (both in `copystages.WRITER_SYSTEM`'s OUTPUT
block): the template showed `em2`-`em5` as `""` so the model reproduced
emptiness, and the closing line still licensed it; LinkedIn asked for only four
keys so `li5` was structurally unreachable.

---

## C. COPYPROMPTS — SETTLED, DO NOT REOPEN

`COHORT_SYSTEM` (begins line 248, legacy writer shape at 391-394) has **ZERO
references outside `copyprompts.py`** — not in `src/`, `scripts/` or `tests/`.
The canonical path calls only `icp_user`, `extract_user`, `source_url_for`,
`ps_variant_for`. **Dead-path debt, intentionally untouched. Do not reopen
unless caller evidence changes.**

---

## D. RACHELE

    account        2020 Companies / 2020companies.com  (record 2020companies-com)
    contact        Rachele Crumpler, Chief Financial Officer
                   linkedin.com/in/rachele-crumpler-cpa-6a2a973a
                   rcrumpler@2020companies.com
    persona        economic_buyer
    offer          OFFER-A-ECONOMIC-BUYER  {profitability, budgeting}
                   (Offer A composes OFFER-PR-001 + OFFER-BU-001)
    qualification  QUALIFIED_THIN  (re-run live, not stale)
    Second Brain   canonical slug "productive", 50 items all CLIENT_SUPPLIED,
                   26 relevant, profitability AND budgeting present downstream

**STATUS: REVIEW_PENDING / HELD FOR EMAIL VERIFICATION + COPY SAFETY.**
**No Slack approval artifact has been posted.**

---

## E. CRITICAL CORRECTION — EMAIL STORAGE WAS **NOT** A BUG

**DO NOT "FIX" `_candidate_steps`.** It correctly finds `['em1'..'em5']`.
They are withheld because `lint.sendable(contact, policy)` is **False**.

Exact measured decision from `verification.decide`:

    state                 held
    sendable              false
    reason                "contactout says valid but the primary is missing,
                           and policy does not clear on the secondary alone"
    confirmation_count    2
    required_confirmations 2
    confirmed_by          contactout, reoon
    disagreement          false

Provider evidence on the contact:

    contactout    valid
    deliverable   ERROR      <-- THIS IS THE PRIMARY PROVIDER
    reoon         valid  (deliverable true, safe_to_send true, score 98)

Productive policy (`lint.policy_for_record`):

    primary                              deliverable
    secondary                            reoon
    required_confirmations               2
    trust_secondary_when_primary_unknown False
    disagreement                         hold

**THE HOLD IS CORRECT.** `CLAUDE.md`: *no email is generated for an unverified
address.*

**DO NOT modify** `verification.py`, `lint.sendable`, the Productive
verification policy, or `_candidate_steps` to force Rachele through.

**An earlier diagnosis in this session called this an email consumer/storage
defect. That was WRONG and is corrected here.** The mechanism that made it look
like a bug: when `email_ok` is False, `email_keys` becomes `[]` silently — no
log, no reason, no counter. TASK-914 adds that log line.

---

## F. OPERATOR DECISION — OPTION 1, ALREADY GIVEN

**Re-run the PRIMARY email verifier (`deliverable`) for
`rcrumpler@2020companies.com`.** This is a provider **READ**/verification
operation and **may consume verification credits**. It authorizes **no**
provider write, enrolment or send.

    IF deliverable returns VALID and policy now clears the address
       -> continue the SAME Rachele through canonical regeneration
    IF deliverable returns ERROR / UNKNOWN / still does not satisfy policy
       -> DO NOT weaken policy. Keep Rachele email HELD, report the result,
          and select another canonical contact/company only after TASK-914
          and the remaining preflight are resolved.

---

## G. TASK-914 — THE REAL CODE DEFECT

    STATE     RUNNING at handoff time
    worker    resonate-qwen-5, branch qwen-worker-5-r23
    claimed   2026-09-29T08:39:29+00:00
    pushed    NOTHING YET (origin/qwen-worker-5-r23 does not exist)

**Do not merge on the worker's word. Verify narrowly and adversarially.**

**The defect:** an unsupported customer-outcome claim shipped through every
gate, in a LinkedIn message:

    "clients using report intelligence have improved resource allocation and
     project margins noticeably. can i share a benchmark example..."

`offers.missing()` already returns *"no documented customer outcomes or case
studies available"* and *"no before-and-after metrics from comparable firms"* —
**the system's own knowledge refuted the claim and the gates still allowed it.**

**Required semantic class (not the sentence):** a customer/client outcome,
improvement, benchmark or typical-result claim **without licensed supporting
evidence** -> REFUSED. Covers: improved margins, improved resource allocation,
increased profitability, reduced costs, saved time, increased revenue.

**LinkedIn must pass through the SAME claim authority as email** — that is
where it escaped. **CLIENT_SUPPLIED still licenses nothing about a prospect.**

TASK-914 also adds Part B observability: when the email branch is skipped for
an unsendable address, log `verification.decide(...)["reason"]`. **The hold
itself does not change.**

**TASK-914 must NOT modify:** verification policy, `verification.py` semantics,
`lint.sendable` semantics, the writer contract, qualification, Second Brain,
Offer Engine.

---

## H. COPY QUALITY — THE RAW ARTIFACT IS NOT APPROVAL-READY

1. The unsupported LinkedIn customer-outcome claim above.
2. **Email 5 subject** `"real-time / project margin / visibility"` — a
   concatenation artifact, not a written subject.
3. **em3 P.S.** was a service list ("retail merchandising, product training,
   display installation") — weak and not a reason to reply.
4. **Opt-out and signature were absent** because the email steps remained
   correctly held by verification policy — `derive_bison_payload` carries plan
   copy only; P.S./opt-out/signature compose in `bisonfactory`/`render`, which
   needs the stored steps.

**Do NOT manually patch these downstream.** After verification clears and
TASK-914 lands, regenerate through the canonical writer and gates.

---

## I. PRE-EXISTING test_generate DEFECT — HARD BLOCKER BEFORE BATCHING

    56 collected · 53 passed · 2 failed · 1 error

    ERROR test_a_draft_that_breaks_a_rule_is_regenerated_not_patched
          KeyError: 'rowan-blake'
    FAIL  test_the_model_is_told_what_failed_rather_than_the_draft_being_edited
          AssertionError: 2 != 1
    FAIL  test_the_retry_names_the_banned_phrase_rather_than_the_code
          AssertionError: 2 != 1

**Measured symptom: `retry_prompts == 2` where the contract expects 1.**

**Bisected: red at `143f132f` (session start) and at every commit since.** NOT
introduced by TASK-910 or tonight's chain — an earlier session's claim that it
was is withdrawn. Also **not** in `docs/state/SUITE-BASELINE-2026-09-26.txt`.

**HARD BLOCKER before autonomous batch processing. Do not silently waive it.**

---

## J. NEXT SESSION — EXACT ORDER, NO BROAD AUDIT

1. Read this handoff.
2. `git fetch origin` and record the exact SHA.
3. Inspect the TASK-914 worker result (`qwen-worker-5-r23`).
4. Verify TASK-914 **narrowly and adversarially**. Merge only if acceptance
   holds. **Do not merge because the worker says PASS.**
5. Re-run primary `deliverable` verification for `rcrumpler@2020companies.com`.
6. Apply the canonical verification policy — unchanged.
7. If Rachele clears, regenerate the SAME Rachele through the canonical path.
8. Require: current qualification, canonical Second Brain, Offer A, 5 emails,
   5 LinkedIn, unsupported claims refused, copylint PASS, render PASS,
   SequencePlan 5+5, projection correspondence, approval hash.
9. Inspect the actual final rendered copy.
10. Only if approval-ready, post the REVIEW_PENDING artifact to `#resonate-os`
    via a review-only path (**no campaign object, no lead, no enrolment, no
    APPROVE/REJECT controls**). Slack transport is live and routed:
    `slack.live()` True, `notify.ops_channel()` -> `C0C3C6MDN9L`.
11. **STOP FOR ZVONIMIR REVIEW.**

**Do NOT begin batching merely because Rachele technically generates.**

---

## K. AFTER OPERATOR APPROVAL ONLY

Fix the pre-existing `test_generate` retry defect to **FULL GREEN**, then run
batch preflight, then zero-write batch generation may begin.

**Batch = 5 COMPANIES, not 5 leads.** One batch may yield more than 5 contacts.

Canonical source: `work/Productive/productive_ICP_safe_to_send (1).csv`,
**33,887 rows**. Per company: qualify -> account research ONCE -> valid
ICP/buying-committee contacts -> person relevance -> Second Brain -> offer ->
strategy -> 5 emails + 5 LinkedIn -> gates -> SequencePlan -> **ZERO-WRITE**
projection -> approval hash -> review artifact. Reuse account intelligence
across contacts at the same company.

---

## L. ABSOLUTE FREEZE

No campaign launch, activation or resume. No provider lead creation or
attachment. No EmailBison or HeyReach enrolment. No prospect-facing email or
LinkedIn. No live canary. **TASK-564 and TASK-565 must pass first.**

---

## M. USEFUL FACTS THIS SESSION MEASURED — do not re-derive

- **Autonomous pool is STOPPED** (`pool_watchdog.sh` killed). Restart with
  `bash scripts/pool_watchdog.sh loop`. While driving a serial critical path,
  use `POOL_ROUND=r<fresh> bash scripts/pool_dispatch.sh resonate-qwen-N:TASK-NNN`.
- **A dirty worker worktree makes `checkout -B` fail** and the dispatch aborts;
  the pool swallows the error. Check `git -C <worker> status --porcelain` and
  `work/worktree-locks/` first.
- **`glm_verify_branch.py` is blind under a non-UTF8 locale** — run it with
  `PYTHONUTF8=1` or it dies on byte 0x90 and returns no verdict.
- **GLM's acceptance-command extractor** reads the FIRST `## Acceptance`
  heading and stops at the next `## `. Commands placed later are invisible.
- **A worktree has no `work/` and no `config/.env`.** For isolated generation,
  copy production `work/` INTO the worktree so ROOT-relative paths resolve
  there, and copy `config/.env`.
- **Merged tasks this session:** 560+907, 904, 905, 906, 908, 909, 910, 911.
  TASK-913 (`qwen-worker-3-r22`) and TASK-914 are NOT merged.
