PRIORITY: READ FIRST

# PRODUCTION HANDOFF — 2026-09-28 midday

**Read this, then `docs/OPERATING-MODE.md`.** Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT.md` on everything it covers.

**Nothing was sent to a prospect. No campaign was activated, resumed, paused,
enrolled or attached. `sending.live` is `off` for `productive`.** Freeze stands.

**TWO PROVIDER ACTIONS HAPPENED, BOTH EXPLICITLY APPROVED, BOTH READ BACK** —
the first in this engagement. Section 2.

## 0. DERIVE EVERY STATE CLAIM

    git fetch origin && git rev-parse master origin/master
    py -3 scripts/claim_task.py --status
    py -3 -c "from src import killswitch as k; print(k.workspace_state('productive'))"

Master moved ~20 times in 18 hours. Any SHA in prose here is historical.

## 1. MASTER SHA

    origin/master   see `git rev-parse` — this line was ccaa48d6 at 11:05

## 2. THE TWO APPROVED PROVIDER ACTIONS

### 2a. UNSUBSCRIBE, STAGE (a) DONE — AND I STOPPED BEFORE (b). ASK THE OPERATOR.

Operator APPROVED (2026-09-28) a staged rollout: (a) one paused Resonate
campaign, read back, report the footer text; (b) then 487/489/493; (c) then the
rest.

**(a) is done and it worked.** Campaign **500**, chosen because it is paused,
ours, and carries **0 leads and 0 sent** — so the write could not touch a
prospect even in principle.

    route   PATCH /campaigns/500/update   -> HTTP 200
    can_unsubscribe   false -> TRUE
    updated_at        provider's own timestamp
    EVERYTHING ELSE UNCHANGED: 2 of 29 fields moved. status still `paused`,
    limits 15/15, total_leads 0, emails_sent 0.

The existing name and limits were sent back unchanged alongside the flag,
because that route requires `name` and this provider is known to discard fields
silently — so all 29 fields were compared, not just the one of interest.

**WHY (b) HAS NOT HAPPENED, and this is the open decision.** The approval
required reading back *what footer text it produces*. **That is not readable:**

- `unsubscribe_text` is `None`, so the provider supplies its own text;
- the campaign's stored sequence bodies contain no unsubscribe string at all;
- so the footer is injected by the provider at send time and no API read shows
  it. The only way to see the exact text is to **send**, which is forbidden.

The switch is proven ON. **The text is UNKNOWN**, which is neither "failed" nor
"wrong" — and UNKNOWN is never PASS here. 487/489/493 send to real people, so
enabling an unseen footer on them is the one thing this staging existed to
prevent. **Options put to the operator: (A) look at campaign 500 in the
EmailBison UI — it is paused and empty, so it is safe to inspect — then confirm;
(B) set our own `unsubscribe_text` so the text is ours and knowable, which is an
operator content decision; (C) proceed blind, not recommended.**

### 2b. ONE CLIENT MESSAGE DELETED, APPROVED, READ BACK

The 08:03 bot post in `#productive-resonate-outbound` (Slack Connect, the client
is in it) showed an absolute path on the operator's laptop **including their
Windows username**. Operator APPROVED deleting that one message.

    chat.delete ts 1790575395.581809 -> ok: True
    read-back: message GONE, no local path anywhere in the channel,
               nothing else posted by us

## 3. THE WEEKLY CLIENT REPORT IS DISABLED, FAIL-CLOSED

`WEEKLY_CLIENT_POST`, absence means off, asserted — the same contract as
`sending.live`. **The preview still goes to `#resonate-os`**, deliberately: a
review pause must not become a blind spot. The hold records as a STOP rather
than a FAILURE, because FAILED retries inside the same window.

**What the client actually saw** is quoted verbatim in the commit and in
`src/weeklyreportwatch.py`. The alarming internal content — the ledger warning
and the 1,504 unplaceable accounts — **stayed internal**.

**Those two lines explained, because they are one problem:** the send ledger for
this workspace is EMPTY. Independently confirmed: across 681 records there is
**not one** recorded send event. EmailBison sent; those events were never
ingested. The "1,504 accounts cannot be placed" figure measures that blind spot
from the other side — it is not 1,504 companies nobody contacted. **The real fix
is ingesting provider send events back into the queue**, and it is not the same
work as editing the report's wording.

## 4. TASK-425 — THE ARTIFACT EXISTS AND IS PUSHED. NOTHING IS LOST BY /clear.

**CORRECTION to an earlier statement in this handoff: the artifact DOES exist.**
I reported it missing while the run was still executing; checking the remote
rather than the running agent showed it had already been committed.

    branch  origin/task-425-one-account-dry-run
    head    88649410
    docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md     the full technical artifact
    docs/TASK-425-FINDINGS-2026-09-28.md              the findings
    docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md      the Croatian operator summary

**Result: three of the four frozen criteria PASSED, one BLOCKED** — the sender
signature, which is launch blocker 3 and was the expected block. By the
operator's own definition ("three passes and one honest BLOCK is the successful
outcome"), that is a pass of this task. Provider writes 0, proven by two
interceptors on the single chokepoint, **both deliberately fired** against the
real EmailBison host, because an interceptor never triggered looks identical to a
clean pass. The matrix carries a fifth control run — the same input twice — since
without it no diff would be evidence, the model wording varying each time.

### WHAT SURVIVES A /clear, AND WHAT DOES NOT

**The work, the artifact, the findings and the Croatian summary are all on the
remote and survive anything.** Nothing important is lost.

**What does NOT survive:** the running subagent's final narrative report. It is a
background subagent of the session, not a shell, and its completion notification
is delivered into that conversation — so after a `/clear` the process may or may
not continue, but its closing report is unreachable either way. That report adds
commentary, not artifact.

### HOW TO RESUME, if anything more is wanted from it

Do NOT re-run the task from the brief — it would redo hours and could reach
different copy. Instead:

1. `git fetch origin && git log --oneline origin/task-425-one-account-dry-run`
   and read the three documents above. That is the deliverable.
2. **Do not merge that branch until `ISSUE-054` is ruled on** (below).
3. If a further run is genuinely needed, dispatch a fresh subagent with
   `docs/BRIEF-task-425-one-account-dry-run.md` **plus** the instruction to start
   from `88649410` rather than from scratch, and to treat the existing artifact as
   the baseline to extend.

### ISSUE-054 — THE OPEN RULING Everything that blocked it is merged and
verified: TASK-426, TASK-364, the dry-run safety path, TASK-400, TASK-427,
decision B, the copylint finality fix, and the research-pack shape fix.

**ISSUE-054, the operator's to rule on before that branch merges.** The agent's
own first fix made `no_repetition/subjects` **structurally incapable of firing**
on the staging path — every configured cadence declares exactly one thread
starter — and its commit claimed the check "keeps its whole power". It did not.
**256 of 1,323 stored contacts flipped from refused to accepted** with that check
as their only failure. An adversarial review caught it, not the author.

**None of this is on master — the branch is unmerged, so there is no live
exposure.** The check is now fixed properly (it takes a thread map, compares one
subject per thread, and warns when it had fewer than two to compare). But those
256 still pass after the correct fix, because what had been refusing them was
looking at the wrong thing. **Whether those 256 are genuinely sendable is the
operator's call. Do not merge that branch until they rule.**

## 5. ICP AUDIT — COMPLETE, NOT MERGED, NOT APPLIED TO PRODUCTION

Branch `task-430-icp-verdicts-491-500`, head `40e4360c`.

    665 companies / 752 contacts across 491-500
    WOULD NOT pass today's ICP gate:  32 companies (4.81%) / 34 contacts (4.52%)
    of those, ALREADY SENT TO:        18 companies / 18 contacts — ALL in 491
    send status UNKNOWN:              16 contacts (492,494,495,497,498) — not zero
    NONE of the 32 is in 493, the only campaign still sending
    verdicts: 633 qualified / 7 not qualified / 25 hold-unknown / 0 error
    cost: ZERO, measured — the classifier is deterministic code, no model

**The caveat that matters more than the headline:** all 633 passes are tier C,
`confidence: low`, `evidence_count: 0`, resting on four structural fields.
`sequencegate` reads only the status word — not tier, score or confidence — so
tier C at low confidence passes exactly as tier A would. **"95% pass" is not the
reassurance it looks like.**

Verdicts were written to a **copy**; production is byte-identical. Applying them
is a separate operator decision, and **a verdict recorded today does not make a
past send retroactively approved.**

## 6. OPEN OPERATOR DECISIONS

    UNSUBSCRIBE  the footer text is unreadable without sending. A / B / C
                 in section 2a. (b) and (c) are BLOCKED on this.
    ISSUE-054    256 contacts flip from refused to accepted. Section 4.
                 The TASK-425 branch must not merge until ruled on.
    491-500      what to do about the nine campaigns, now that the numbers
                 exist. Section 5.
    ICP VERDICTS whether to apply the audit's verdicts to production at all.

## 7. WHAT THIS SESSION GOT WRONG

1. **Said twice I was dispatching the research-shape task, then didn't** — a
   notification arrived and I handled that instead. Dispatched later.
2. **Reported a cadence mismatch as blocking TASK-425.** It was not: a NEW
   campaign gets the canonical five-plus-five. I read the reason off a refusal
   message, and **a refusal names the gate that fired, not why it fired.**
3. **First baseline diff reported "128 new and 128 cleared"** — compared the
   baseline's `FAIL `/`ERROR `-prefixed strings against bare test names.
4. **Reset a worktree while its own suite measurement ran inside it**, voiding
   two hours of measurement.
5. **Put a critical-path brief in `docs/qwen-tasks/TODO/` marked "CLAUDE ONLY"**,
   then found no such filter exists. Three Qwen workers subsequently claimed work
   they should not have. **`STATUS: BLOCKED` is the only marker `claim_task.py`
   honours** — `DEPENDS:` is not read by the readiness check, and a comment
   naming an owner is read by nothing.
6. **Lost a phrase from a merge message to shell command substitution** —
   backticks inside `-m`. Use a heredoc.
7. **Concluded a handoff file was missing** when `ls` printed nothing — it had
   failed on an invalid `--time-style` argument. The file was always there.
8. **Built the unsubscribe route without its leading slash** and got a 404. The
   write did not take and nothing changed, which is the only reason it was
   harmless.

## 8. THE FIRST THREE ACTIONS FOR THE NEXT SESSION

1. **Read the operator's answer on the unsubscribe footer** (section 2a) before
   any further provider write. (b) and (c) are blocked on it.
2. **The TASK-425 artifact already exists** on
   `origin/task-425-one-account-dry-run` at `88649410` — three criteria passed,
   the signature BLOCKED as expected. Do NOT re-run it. **Do not merge that
   branch until ISSUE-054 is ruled on**, and no ten accounts.
3. **The empty send ledger** (section 3) is the largest unaddressed defect: the
   provider's send events are never ingested, which is what makes 1,504 accounts
   unplaceable and the weekly report misleading. It needs its own task.
