# Production handoff — 2026-09-24 late

Written at 97% context. **Supersedes `PRODUCTION-HANDOFF-2026-09-24-EVENING.md`
for state; that file's "TOMORROW, IN THIS ORDER" section still stands and is
restated at §7 with tonight's additions.**

Lane 1, production. FOCUS directive to 2026-10-01.

---

## 1. THE ESTATE

    campaigns   10 active · 0 paused · 1 archived (495) · 1 new empty (500)
    monitors    21 derived, all UP on two witnesses
    blanks      0 pending anywhere
    sent today  0 in our campaigns, provider-confirmed
    forward book  census COMPLETE and fresh — 14/14 campaigns walked

**491 and 481 are both active**, resumed on operator authority.

**Campaign 500** exists: `…EU-HOURS - BATCH1B - LUKA`, created and sequenced
(steps 4775/4776/4777), **0 leads, paused**. Left deliberately, not deleted.

**63 leads are stopped and waiting.** They were attached to 496/497/498
tonight, then stopped because all three carry settled blank rows from the
incident (11/9/4). Re-pushing them refused — see ISSUE-035.

---

## 2. WHAT CHANGED TONIGHT

**Merged and pushed:** infra `6ff9cc94` (write ledger, sealed resume verb, one
log per watcher), slack-agent (researchpack + copylint), `EMAIL_RESUME` into
SUPPORTED, `testidentity` corrected to the real domain, the 50% forward-book
ceiling, four new register rows, and **the four approved step-4/step-5
templates in `src/cadence.py`**.

**The cadence is HALF-APPLIED AND MUST BE FINISHED BEFORE ANY PUSH.** The
templates exist; the config does not agree with them yet. `bisonfactory`
REFUSES when the provider sequence keys and the cadence keys disagree, so
until all four of these land together, a push fails in a place that does not
name the cause:

1. `config/clients/productive.yaml` `email_sequence.steps` still declares
   em1..em3. It needs em1, em2, em4, em5 — **`breakup` is retired**.
2. `thread_reply_pattern` is `[false, true, true]` and needs a fourth entry.
   em4 opens a NEW thread (false, SUBJECT_2); em5 replies into it (true).
3. `CADENCE_STEPS` in `scripts/batch1_build.py` must gain the same keys.
4. Final step `wait_in_days` must be **1, never 0** — campaign 485 was left at
   0 steps by exactly that.

**Then S7 re-renders all 927 rows.** `s7-copy.jsonl` carries `subject_1` and
`body_1..3` only; em4/em5 need `subject_2`, `body_4`, `body_5`. Verified on 40
live leads tonight: those variables are **empty, not the literal `'None'`** the
morning handoff warned about — so that hazard is not present today, but empty
is what the blank gate refuses.

**I had this order backwards earlier and corrected it:** cadence templates
first, then the config, then S7. S7 cannot render a body whose template does
not exist.

---

## 3. THE TWO BACKGROUND AGENTS — COLLECT THESE

Both are Claude agents in their own locked worktrees. Both were told to commit
work before verification and to cap any full-suite run at one pass.

### 3.1 S5 — PROGRESSING, has committed

    worktree  .claude/worktrees/agent-ab11d67ddc0840181
    branch    worktree-agent-ab11d67ddc0840181
    HEAD      97832f0e  "S5 bought 22,000 credits with no ledger row"

Four operator decisions it was given: repoint to the amended S3 pair, K sized
to the providers actually called, retry-once-then-park for the 23.5%
RETRYABLE re-buy, and **every S5 call through `spend()`**.

**CHECK THE LAST ONE AGAINST THE FILE, NOT THE REPORT.** It was observed
restoring `src/spendledger.py` to HEAD. If that means the ledger wiring did
not land, its "done" is wrong. Earlier measurement, already committed: K=3 was
sized in a comment against **ContactOut's 60/min — a provider this script
never calls** — and K=8 measures 4.1× faster.

### 3.2 Unsubscribe classification — NOTHING COMMITTED

    worktree  .claude/worktrees/agent-a229ee3cba3357ce9
    branch    worktree-agent-a229ee3cba3357ce9
    HEAD      deb4b1e3  — which is the commit it STARTED from

**Roughly two hours with no commit of its own.** Whatever exists is
uncommitted in that worktree. It has been told to commit even if incomplete.
A fresh session should look there first and salvage rather than restart.

Its task: the operator removed the unsubscribe LINK, so **the reply is now the
only opt-out**. `replies.UNSUBSCRIBE_PATTERNS` is 14 entries, **all English,
with no bare "stop"**, against an estate sending to nineteen countries. This
is ISSUE-024 recurring on the one path that carries the whole obligation.

---

## 4. THE QWEN POOL — TODO DEPTH IS 1, WHICH IS A CRITICAL

The operator's standing rule is a TODO of **at least 10** written tasks, and
below 5 is a CRITICAL. **It is at 1.** I wrote four tasks and did not write
the ten; that is the gap, and four workers are idle behind it.

    TASK-275  account-rule + collision-gate RED tests   DONE   qwen-2, r9
    TASK-276  Apify cost calibration                    BLOCKED  boundary hit
    TASK-277  copylint wiring                           DONE   qwen-4 — DO NOT MERGE, §4.1
    TASK-278  spend report from provider balances       DONE   qwen-5

**None is on master. All want the two-pass Qwen review first.**

### 4.1 TASK-277 must not be merged — I read it myself

It claims *"the copy lint is on the send path, not merely present."* It is not:

- `run_with_copylint` is **called by nothing** — only its own `.pyc` matches.
- All 8 tests call it **directly**; 0 call `push.run(`.
- `src/push.py` is **not the send path**. Its `run()` raises on `live=True`:
  *"live push is not implemented in this build… No code here can reach
  EmailBison or HeyReach."* The real path is `scripts/batch1_push.py` →
  `bisonfactory.stage`.

So the lint was wired into a module that refuses to send, through a function
nobody calls, proved by tests that call it directly. **That is the exact
defect the task was written about, reproduced by the fix for it.** The wiring
belongs in `bisonfactory.stage` before the attach, and the test must assert on
the push refusing.

### 4.2 The ten to write

Named by the operator: the 19,612 pack fetch in chunks, the reverse
reconciliation sweep, the re-engagement provider read for UK/EU, the spend
report wired into the Monday report, the 4-step S7 render verification — then
MX walk, collision walk, suite baseline by name, register hygiene, and
second-pass reviews of tonight's four deliveries.

---

## 5. THE STOP MEASUREMENT IS BLOCKED, AND NOT BY CAPACITY

The operator is waiting to reply by email. **I could not signal, and would not
have signalled a meaningless pass.**

    HeyReach 613744  zbeslic  leadCampaignStatus: "Finished"
    EmailBison       no lead on the corrected address at all

A stop against a **finished** lead returns "already settled" — a pass by
construction. That is the shape of the first blank-content halt, which alerted
and halted nothing and read as working.

**And the LinkedIn side cannot be made live from here.** `LINKEDIN_ADD_LEAD`
is CONDITIONAL and refuses unless a provider read at the moment of the write
proves the destination cannot send: *"Only DRAFT proves that. PAUSED does not.
FINISHED does not."* 613744 is `IN_PROGRESS`. The gate is working.

**Either unblocks it:** the operator re-adds themselves to 613744 in the
HeyReach UI, or authorises a DRAFT LinkedIn test campaign to add them to.
Then ~15 minutes: create the email lead on the corrected address **with copy
variables** (`_refuse_unvariabled_leads` refuses the attach otherwise), attach
to 491 (0 pending blanks), confirm `in_sequence`, post "reply by email now".

**Why it matters:** the email→LinkedIn direction has never been exercised
against a live lead. `heyreach.stop_lead_in_campaign` exists and is wired —
its own docstring says **NEVER LIVE-VALIDATED**. The LinkedIn→email direction
passed at 7.7 minutes on 09-23. The halt condition is both ways under 15.

---

## 6. FIVE THINGS FOUND TONIGHT THAT OUTLIVE THE SESSION

1. **A routine command arms a silent drop of our own replies.**
   `inbound.OWNED_CAMPAIGNS = {605732, 605487, 604869, 599020}` are HeyReach
   ids; `_positively_not_ours` compares an EmailBison event's campaign id
   against them without asking which provider it came from. An EmailBison
   reply on our own 491 reads as "provably not ours" and is dropped.
   **Latent only because `_owned()` refuses on a stale readback — and
   `provider_truth.py` refreshes it.** DO NOT RUN IT until fixed. Operator has
   ordered per-provider resolution from the registry.
2. **The notifications channel: 103 posts in 72h → 4.** Of the 103, **99 were
   the client's own traffic and 2 were ours** — two real unmatched replies on
   HeyReach 613744, invisible in the noise for three days. Branch
   `notifications-repair` @ `c0855fd3`, pushed, not merged.
3. **`bison.fetch_events` carries 11 event types, not the 8 I reported this
   morning.** Six normalise to `unknown`, including
   **`EMAIL_ACCOUNT_DISCONNECTED`** — a sender mailbox that stopped working,
   with no alert on it.
4. **All three Apify actor ids in the merged package were invented** (404),
   and the cassettes matched the same invented names, so ~30 tests were green
   against actors Apify has never heard of. Real actors now measured:
   **$0.03987/account, $781.94/month at 19,612 — 3.93× over the $199 Scale
   budget.** The website crawler is 72% of it; the operator has ruled that
   site content comes from our own free crawler and Apify runs LinkedIn only.
5. **50 of 71 job rows were a different company** — `companyName` is a text
   filter, not an identity match. It would have put a stranger's open roles
   into a client's personalised email. Guarded, failing closed.

---

## 7. TOMORROW, IN ORDER

1. **Retire the `last_touch` cache.** Every decision reads the last confirmed
   touch from the provider's sent rows at decision time. Test: a lead sent
   yesterday can never read as untouched for 90 days. Measured: 145 of 2,081
   rows staler than the live lead, worst by 111 days; lead 133283 read 111
   days untouched while its last send was two days earlier from our own 491.
2. **The account rule and the collision gate, together.** Same contact never
   twice; same account new persona after 5 days with no human reply; third
   after 7 more; any reply or unsubscribe at the account stops all others;
   **a stop carrying our own reason plus an operator-recorded move is not an
   account-level hold** (ISSUE-035). Tests first — TASK-275's are written and
   red. GLM review before merge.
3. **Finish the cadence (§2), then S7 re-render, then push.** Fresh campaigns
   501 and 502 for Bojan and Jakov beside 500 for Luka; the **128 clean UK/EU
   leads** go in under the gate. The 63 stopped leads wait for step 2.
4. **The stop measurement** the moment the LinkedIn side is live (§5), then
   the 825 enrollment across 33 seats at 25/seat/day if it passes.
5. **Draft rung 3** — name Productive, one capability, one consequence, per
   persona — for approval, to take the cadence from 4 steps to 5.

Also standing and not yet applied: HeyReach sending 07:00–23:00 seven days a
week at full seat limits across all 33 campaigns; continuous pushing the same
hour a cohort clears; packs on every push with coverage reported.

---

## 8. THE PATTERN, AND MY OWN ERRORS

**Four times today I asserted absence from a lookup I had not verified.**
`subject`/`body` on an object whose keys are `email_subject`/`email_body`, and
I reported five empty steps and refused a campaign on it. `hasattr` on
`heyreach.stop_lead`, a name I invented, and I told infra to build something
that already existed. Two counts of 9 among the same 23 records, joined in
prose, never cross-tabulated. A `sed` range spanning two functions that made a
wired thing look unwired and then unwired look wired.

**The check that costs ten seconds and caught every one:** print the object's
keys, `dir()` the module, read the actual lines. `None` from a `.get()` is not
evidence of emptiness; `False` from a `hasattr` is not evidence of absence.

**And one that was not a lookup:** I let background agents run in the main
checkout after being warned, and one left it on a feature branch — so a
production commit went to that branch and `git push origin master` pushed an
unrelated agent's work instead. Every code-editing agent now gets its own
worktree; the main checkout belongs to the foreground session alone.

**The recurring one, stated once more because it held all day:** every
headline number came from a stage that had not asked the next stage's
question. 1,508 exportable that was 114. 19,612 "IN" of which two-thirds are
under the floor. 330 selected of which 212 were spoken for. 8,595 never
verified that is really 14,086. A 19:00 ETA sized on a builder whose input had
expired six hours earlier. In every case the later gate was right.
