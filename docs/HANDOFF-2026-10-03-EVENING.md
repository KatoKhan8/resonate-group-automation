# Handoff — 2026-10-03, evening. For a session with none of this conversation.

Written because the scratchpad reached 785k tokens and the context is being
cleared. **Everything below is on disk or in git. Nothing here depends on
scrollback.** Every number says how it was measured.

---

## 1. Master, and the reference

    master   2bf7b8a5   pushed, origin/master agrees
    reference  C:\Users\Zvonimir\Desktop\resonate-ops\logs\reference-228-master-2bf7b8a5.log

**228 failing names is the current baseline.** It was 231 this morning; three
names went away and each was positively verified as running and passing, never
inferred from its absence.

### THREE merges landed today, all on the canary minimal path

| merge | branch | why it mattered |
|---|---|---|
| `7e8eee41` | `task-973-write-barrier` | `refuse_production_write` protected `<ROOT>/work` of the tree it was imported from, and every gate suite runs from a worktree — so the MAIN checkout's `work/campaigns.jsonl`, the OS authority, was outside the barrier for every gate run this project has ever done. Measured under `unittest`: this tree REFUSED, main checkout ALLOWED |
| `975c18cc` | `task-word-contract-enforced` | `lint.WORD_CONTRACT` becomes the single authority for a body's word count; em1 is `(90, 120, 140)`; `REPLY_MIN_WORDS`/`REPLY_MAX_WORDS` deleted with all **eight** live readers rewired; the four keyless doors (`approve`, `eligibility`, `executionguard`, `campaigns`) finally have tests — and the per-door mutation table showed each could be switched off with the pre-existing 53 tests **completely green** |
| `2bf7b8a5` | `task-guard-regressions-rebased` | the ownership classifier. Before it, `resonate_internal` appeared in **zero** files under `src/` and `hasattr(providerwrites, "classify_campaign")` was False, so an internal campaign was never refused FOR BEING THEIRS. Now 274/327/328/352 are `resonate_internal`, 481 is `resonate_os`, and junk — `None`, `""`, `"abc"`, `0`, `-1`, `[]` — is `unknown`, which is do-not-touch and never a pass |

Each merge: suite clean as a SET against a reference measured on the master it
merged into, GLM multi-part PASS, and `git diff master <branch>` proven EMPTY
afterwards before the branch's log became the next reference.

## 2. The machine right now

    suite lock   HELD by a QWEN WORKER
                 branch=qwen-worker-r9  pid=116536  since 2026-10-03T18:40:18
                 worktree=C:\Users\Zvonimir\Desktop\resonate-qwen-worker
    queue        0 waiters
    my runs      none alive (0 run_suite processes of mine)

**That lock is not mine and must not be taken.** A live holder's lock is never
stolen; a stale one (PID gone) is taken over loudly. Read the holder with
`src.suitelock.read()` and check the PID with `Get-CimInstance Win32_Process` —
`tasklist` typed in the Bash tool returns zero rows for every query, so a live
PID reads as GONE there.

## 3. What is next, in order

1. **TASK-1004 (`task-1004-positive-replies-reach-a-human` @ `a5729f2a`) — the
   last minimal-path branch.** Its full suite ran (2,898.8s, 14,651 results)
   and carries **exactly ONE new failing name**:

       NEW  test_signals.EvidenceIsMandatory.test_engagement_signals_map_from_the_canonical_outcomes
       GONE test_referral.TheWholeChain.test_a_plain_hand_off_holds_the_referrer

   The NEW one is reproduced and is one decision wide: `'needs_a_person' not
   found in S.ENGAGEMENT_SIGNAL`, `tests/test_signals.py:111`, whose docstring
   is the argument — *"No second vocabulary for facts that already have
   names."* **The mapping to use is `needs_a_person` → `reply`**: conservative,
   matching what the map already does with `neutral`, `negative` and
   `not_icp`, and explicitly NOT `positive_reply`, because claiming a question
   as a positive reply would inflate the one metric the operator has made
   primary. The lane has this and is working on it.
   The GONE one is explained: it is a test somebody wrote as the operator's
   rule and left red, and this branch makes it pass.
2. **Then phase 0 on savagebrands**, which needs TASK-1004 on master because
   without it a positive reply on the canary reaches nobody. Five generated
   emails, the copy-review file, the Slack output to `#resonate-os-output`.
   **GENERATION DOES NOT WAIT for the operator's approval — approval is for
   sending only.** savagebrands is now verified and sendable and is held only
   by `held:approval_stale`.
3. **Then phase 1** (five cases).
4. The unpruned rejection ledger gets its own branch, **before phase 2, not
   before the canary**.

## 4. Every branch, and every one is pushed

    master                                      2bf7b8a5   = origin
    task-defect-map                             (see git)   = origin   docs, tasks, second brain
    task-959-multipart-review                   15bf6eb2    = origin   the gate itself
    task-1004-positive-replies-reach-a-human    a5729f2a    = origin   P0 1-3
    task-copy-exemplars                         68f3601b    = origin   the role ladder, the contract
    task-980-copy-learnings                     c66e2ed1    = origin   second-brain/email.md
    task-981-second-brain-linkedin              6b13e92e    = origin   second-brain/linkedin.md, 121 campaigns
    task-phase2-simclock                        787fa450    = origin   the injected clock, 120-day run
    task-979-verification-is-a-pipeline-step    350bb2d2    = origin   verification reuses what existed
    task-973-write-barrier                      716a0cf7    = origin   MERGED
    task-word-contract-enforced                 874cf0ed    = origin   MERGED
    task-guard-regressions-rebased              fa644547    = origin   MERGED

## 5. Where the durable things live

    C:\Users\Zvonimir\Desktop\resonate-ops\
        logs\        every suite log and every reference, named by SHA
        tools\       refdiff.py (positional args), canarypath.py, copyreview.py
        copy-review\ FINDING-bigfish-2026-10-02.md
                     POSITIVE-SAMPLE-2026-10-03.md  <- 32 rows, real text, the operator's review
        briefs\      canary-minimal-path, phase1, phase2
        glm-verdicts\

    docs\second-brain\   README (the metric is the positive reply; Farseer is the reference)
                         decisions.md  every operator decision, dated, with its reason
                         defects.md    eight recurring PATTERNS, not individual defects
                         positive-replies.md, email.md, linkedin.md
    docs\MORNING-HANDOVER-2026-10-04.md   with the 90-minute monitoring log
    docs\qwen-tasks\TODO\                 TASK-959..977, TASK-1001..1006

## 6. WHERE I WENT WRONG TODAY

Written in full because the next session will otherwise repeat it. Every one
was caught by a control, a reviewer or another lane — **not one by me reading
my own work.**

**Five in one 60-line function** (`summarise_tests` in the gate), each found by
GLM:

1. **Counted every failing test twice.** The failure block repeats each name in
   a `FAIL:`/`ERROR:` header and I counted those as runs. GLM found it *using
   the control line I had just added*: 237 against the run's `Ran 232`, and the
   gap was exactly the failure count.
2. **Reported failures with no baseline context**, so GLM read five of master's
   standing failures as the branch's regressions and failed a branch whose
   suite then measured 228 against 228 with 0 new.
3. **A two-line verdict window** missed three verdicts sitting behind a
   `ResourceWarning`, where unittest's `ok` lands alone on its own line four
   lines below the name. "40 ran, 37 ok, 0 failed" invited GLM to infer hidden
   skips in a contract module. There were none.
4. **The wider scan then read the run's own final `OK`** as a test's verdict —
   caught by the control I wrote for defect 3, within minutes.
5. **Reported two `NEEDS_CLAUDE` parts to the operator without reading why.**
   Both were `GlmTimeout` — A42, the adapter's 180s ceiling — so "the reviewer
   abstained" stood in for "the call never happened". The gate now retries once
   and says *"a tooling limit and NOT a finding about the code"* in those words.

**And six more:**

6. **Launched a full suite on MASTER by mistake.** The `cd` into the P0
   worktree failed, I had not chained it with `&&`, and I did not check the cwd
   before launching. The kill was refused by the Claude Code classifier, so I
   queued the real run behind it rather than working around the refusal. Cost
   about 45 minutes of lock. **Verify the tree before launching; the lock's own
   `worktree` field is there for exactly this.**
7. **Compared name sets with one side carrying a `tests.` prefix**, and
   reported 5 new and 5 gone for the same five tests. That is the defect the
   gate's own test module pins in its first paragraph — *"the two sides were
   shaped differently and nobody reconciled them"* — and I walked into it.
   Shape both sides before comparing, every time.
8. **TASK-974's acceptance command read only the `commit` key** and missed
   `measured_at_commit`, so it passed vacuously on the very next branch.
9. **The same command globs only `SUITE-*.json`** and would have missed
   `NAME-DIFF-*.json`, which is where the guard's stale artefact actually was.
10. **TASK-1001's command matched the bare word `call`** and hit
    `provider_call_started` and six siblings — API calls, not phone calls — so
    it passed while measuring nothing.
11. **Committed a red state with a message claiming "all green."** Corrected in
    a following commit rather than amended, so the record keeps what happened.
12. **Put the client's domain in two files I wrote**, one of them in the row
    explaining that the domain is on the roster. Ninth instance of that pattern
    in two days. Found by another lane reading the file.
13. **Said savagebrands "was never verified."** It had ContactOut `valid` AND
    Reoon `valid` at score 98, 20 days old; I had read EmailBison's own
    `status` field, which is a different fact. The real hold was that
    Productive's policy names `deliverable` as primary and that row was a local
    refusal.
14. **Quoted a reply-class distribution that matches none of the three
    classified artefacts on disk** — and the deeper finding is that three
    artefacts of the same 899 replies exist and no two agree, so a count from a
    classification has to carry that run's identity.
15. **Re-derived TASK-965's measurements that were already written in its own
    file.** The handoff told me not to repeat finished research and I repeated
    it anyway.

## 7. DO NOT RE-INVESTIGATE

- **savagebrands' verification.** Settled: ContactOut and Reoon both `valid`,
  the hold was `deliverable` being the policy's primary with no answer, and
  verification is now a pipeline step on `task-979`. It is verified and
  sendable and held only by `held:approval_stale`.
- **Whether the five red tests on 943 were the branch's.** They were master's.
  Measured on a neutral worktree detached at master with nothing from the
  branch present: same five names, same counts, all five in the reference.
- **The em-dash "regression".** `_PUNCTUATION_MAP["—"]` became `", "` on
  2026-09-30 because the old `" - "` output WAS the banned pattern. The tests
  pinning the old chain were written two days earlier and never moved.
  `lint.check` on a raw em dash still refuses: no em dash reaches a prospect.
- **The nine writer retries.** That is `MAX_WRITER_ATTEMPTS = 10`, raised
  3→6→10 deliberately. The real defect is the unpruned rejection ledger.
- **Farseer.** Not on EmailBison (all 40 read), not on the HeyReach seat (all
  121 read), not a client config here. The repo trace is the client's own
  domain on `config/suppress.local.txt` and eleven Slack-history files. It ran
  on LinkedIn, voice, WhatsApp and the phone; the channel model has **two**
  channels, so three of those cannot be recorded at all. TASK-1001/1002/1003,
  and access comes from the operator.
- **"35 meetings in 14 countries."** The email lane found **56 meetings
  invoiced** Feb–Jun 2026; "35" and "countries" never co-occur with the client
  across 165 Slack messages, and country is never a field. This system can
  neither confirm nor refute either number — that is TASK-1002.
- **Whether `claims.customer_outcome_claim` is dead code.** It is not.
  `claims.py:747` calls it inside `check()`, and `generate.py` calls `check` at
  eleven sites. The 153-tests-to-2-src reading was wrong.
- **Whether the task numbers collide.** They do: three lanes independently took
  980 and 981 because nothing allocates them. The operator has asked for an
  allocator with a counter and a lock; the collisions are still unresolved.

## 8. The open decisions the operator has NOT yet made

1. **USD per credit for Deliverable and Reoon.** `spendledger.USD_PER_UNIT['credits']`
   is `None` — *"NOBODY HAS PRICED IT, and that is a real answer."* Batch 3 of
   verification (483 contacts, up to 1,311 credits) is not evaluable against
   any cap until it is set.
2. **A third channel's vocabulary** (TASK-1001): `phone` and `whatsapp` as
   channels, or one `manual` channel with a sub-type. The second is smaller.
3. **The 21 unmatched phase-2 scenarios** need classifying into defect / no
   rule / wrong scenario, and the "no rule" list is the operator's to decide.
4. **The task allocator** and the three collided numbers.
5. **TASK-1006**: two offer selectors disagree, and the acceptance commands
   PASS on master and FAIL on the branch — the table is in the task, because
   running them on master would read as fixed.
