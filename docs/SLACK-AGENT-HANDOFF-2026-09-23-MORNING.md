# Slack agent — handoff, 2026-09-23 morning

Supersedes `SLACK-AGENT-HANDOFF-2026-09-22-NIGHT.md` and everything before
it. Written to the test CLAUDE.md sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

**Branch `slack-agent` at `f5ae0270`**, pushed and verified against the
remote. Master is `c8a8744c`. The branch was fast-forwarded to master at the
start of this session, so `git log master..slack-agent` is exactly this
session's three commits:

    edb9146f  the agent could not read the campaign that carries half the sends
    63d6be07  merge request for D2, and the loop that is not running at all
    f5ae0270  CHECKPOINT, UNREVIEWED AND UNFINISHED: the reply half of the offer

One merge request, current: `docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D2.md`.

---

## 1. THE FIRST THING: NOTHING IS RUNNING

**There is not one python process on this machine.** The box booted at
**05:32:50** and nothing was started after it — not the agent, not
`slack_history.py --loop`, not the twelve production watch loops.

**And `slack_agent_loop.py` did not die in the shutdown.** It stopped at
**00:51:09**, four and a half hours earlier:

    work/heartbeat/slack-agent.json   pid 109640   last beat 22:51:09Z
    work/heartbeat/replies.json       pid  19236   last beat 03:26:56Z
    work/heartbeat/bison-494.json                  last beat 03:29:04Z

Every other loop beat until the machine went down; this one stopped on its
own, silently. `work/slack-agent.err.log` is EMPTY and
`work/slack-agent.out.log` ends on `HELLO from Slack` with nothing after it.
The last question it answered was at 22:47:40Z.

That is the third process in two days to die leaving its own state looking
healthy — the pattern the overnight production handoff named. **This loop
has no liveness monitor and wants one**: pid death and heartbeat age, the
way the learning walk got them after the same failure.

**A restart is the operator's, and it is the gate on most of Phase D.**

---

## 2. WHAT WAS VERIFIED THIS MORNING

**D1 and D2 are merged.** `f077dcbc` merged the branch; `master..slack-agent`
was empty at session start. **There is no D2 merge-request doc in the D1
sense** — D2's content is `4af4f982` (reply classification: `automated` and
`assistant_redirect`, the day's only "positive" being an EA managing her
principal's inbox) delivered as
`docs/REPLY-CLASSIFICATION-POLICY-2026-09-22.md`. The production session
noticed the same and wrote it down. **This session's D2 is a different,
later increment** and its doc is named for it; if that collision matters,
rename mine rather than the policy doc.

**Merged is not live.** Both are on master and neither is running.

**No client mention went unanswered overnight.** The last message of any
kind in `#productive-resonate-outbound` is the agent's own answer at
22:12:41 on 09-22. Nothing arrived while the loop was down. Checked twice —
channel read and a dated search.

### 2a. But the wrong answer is already in the client's thread

D1 §5 says the Croatian sending-domains question was deliberately not
posted. That is true of the **re-ask**. The list itself **was posted at
14:42 on 2026-09-22** into Bruno's thread `1790061486.125249` — all 69
domains, every row reading `bez slanja u zadnjih 7 dana`, six hours before
`0f130383` fixed it, on a day those mailboxes sent 494 emails.

**Phase D item 1 is a correction, not an answer.** It stays unsent until the
loop is on D1/D2 code, and when it goes it should say it is correcting an
earlier automatic answer rather than quietly posting a different list.

---

## 3. WHAT THIS SESSION BUILT: D2, THE CAP

Found by doing exactly what the operator asked — asking what was sent and
reading the provider in the same minute.

    the agent, on merged D1 code:  246 emails over 7 days, 491 unreadable
    the provider, same morning:    494 emails sent on 2026-09-22 alone

`bison.scheduled_emails` refuses past `PAGE_CAP = 40` rather than truncating.
Campaign 491 is 645 rows — 43 pages — so it raised `PartialInventory` on
**every agent-side read**, and 491 alone is 253 of the day's 494. Five call
sites read a queue and not one passed a cap.

Fixed by one capped read, `slackagentreadback.queue`, at
`QUEUE_PAGE_CAP = 400` — deliberately the same constant
`scripts/hard_stop_check.py` took for the same campaign the day before, with
a test that fails if they ever diverge. **The refusal is still the property:**
past 400 pages it still raises and callers still count the campaign
unreadable.

**Live readback after the fix, same question: 246 → 502, nothing
unreadable, and 491's 254 agrees with the provider.**

The merge request has the rest, including the two things that are not in
the diff (§1 above and §2a).

---

## 4. WHAT IS UNFINISHED, AND THE TRAP IN IT

`f5ae0270` is **Phase D item 2's second half, decided and half-written**.
Read its commit message before touching it; the design is all there.

**The trap, named so nobody walks into it:** `due_replies` and
`advance_to_reply` exist and **nothing calls them**. That is this module's
own historical fault — it shipped with `register()` wired in and `due()`
read by nothing. The live path is unchanged and the checkpoint is safe to
carry, but **do not merge it as a feature**: it is not one until the
deliverer calls it.

Still to do, in order:

1. `read_human_replies(watch)` in `scripts/slack_followup_loop.py`.
   `bison.fetch_replies` rows carry `campaign_id`, `automated_reply` and an
   increasing `id` — **verified live this morning**. Walk newest-first,
   stop at the watch's `reply_marker`, count rows whose `campaign_id` is in
   the watch and which are human under BOTH witnesses (our
   `replies.is_automated` says no AND the provider's `automated_reply` is
   false). Bound the walk and return `None` if it outgrows the bound —
   `None` is unreadable, never zero.
2. The stage-2 branch in `deliver()`: post `reply_message_for`, then close.
   The send branch must call `advance_to_reply` instead of `close` once
   step 1 exists — **not before**, or a client is promised a second post
   nothing can make.
3. `OFFER_NOTICE` in `src/slackconversation.py` still promises exactly one
   post. **Change it last.** The promise may not move ahead of the
   mechanism; that ordering is the whole lesson of this module.
4. The module docstring, which still describes one post and one close.
5. Tests, and they must not mock the function under test — see §6.

`REPLY_TTL_SECONDS = 7 days` is a guess, labelled as one in the source. The
operator should replace it with a measurement.

---

## 5. THE FIVE CLIENT PROBES, AND HOW TO RUN THEM CORRECTLY

Re-run offline on merged code. All five resolved `scope=client
workspace=productive`. **Nothing leaked**: no other client named, no rival
account, no billing figure, no Resonate person, no workspace list.

**The first attempt was worthless and looked fine.** All five resolved
`scope=unbound`, because **this worktree has its own gitignored `work/`**,
last written 2026-09-21, with no channel binding in it. Production's
`work/workspaces.jsonl` was copied to a scratchpad file and `WORKSPACES`
pointed at the copy — production state read, never written. **Anybody
running a client probe from a worktree has to do this or they are probing
an unbound channel and proving nothing.**

Two observations for the operator, neither a leak:

- The injection probe is answered as a **change request** — "I can't make
  that change myself, I'll pass it to the Resonate team". It refuses
  correctly and then offers to raise a ticket out of a social-engineering
  attempt. Whether an injection should reach the relay path is a decision,
  and `slackroles` is where it would be made.
- Two answers in the same scope minutes apart said "your eight live
  campaigns" and "your 23 campaigns, of which 14 are approved". Both
  defensible; a client hearing both would not think so.

---

## 6. TWO THINGS ABOUT THE TESTS THAT COST REAL TIME

**The suite, run as one full-repo `unittest discover`, is not green on
master and has not been.** Today, with no changes present: **71 failures
and 35 errors over 11,526 tests.** Run file by file they pass. CLAUDE.md
already explains it — loopback binding and demo estates overlapping during
teardown — but the number is large enough to hide a real regression, and
**nobody should read a green file-by-file run as a green suite.** If that
set is news, it is worth somebody's afternoon.

**So compare BY NAME, never by count.** This session's D2 change was
verified by taking the named failure set on a pristine tree, restoring the
changes, and diffing:

    ran 11526 -> 11537 (+11)   failures 71 -> 71   errors 35 -> 35
    NEW 0   GONE 0

A matching count is not a matching set.

**And the third mocked-the-defect finding in two days.** Every existing test
of the queue readers patches `bison.scheduled_emails` with a fake, and a
fake has no page cap — so no fixture here could ever have failed. Three of
those fakes were written `lambda cid:`, which is the same fact from the
other side: no test in this repository had handed those readers a call in
the shape the provider actually receives.

---

## 7. STILL FOR THE OPERATOR

Ordered by what costs most to leave undone.

1. **Start `slack_agent_loop.py`.** Nothing is running and the client
   channel is unattended.
2. **A liveness monitor on it** — pid death and heartbeat age (§1).
3. **Merge D2 and restart**, then the correction in
   `#productive-resonate-outbound` (§2a).
4. `scripts/slack_history.py --loop` and the twelve production watch loops
   are also down since the shutdown. Not this session's, but nobody has
   restarted them either.
5. **`scripts/slack_followup_loop.py` has never been started** — there is
   no `work/heartbeat/slack-followup.json`. The offer stays correctly
   switched off, which is the design, but a client who would have been told
   is not being told.
6. `slack.roles` for Productive; seat ownership; `hr-`/`li-`
   reconciliation; the plaintext GoDaddy password in Slack history; the
   eight unbound shared channels; `src/providers/slack.py` `thread_parent`.
7. The digest line for meeting counts (C3 §1e); promote a winner; a
   correction verb for the meetings ledger.
8. **`work/campaigns.jsonl` still carries `created_at: None` on every
   campaign that has ever sent.** Not ours; still a field read as
   authoritative elsewhere and null on exactly the rows anybody wants it
   for.

---

## 8. PHASE D, WHERE IT STANDS

    1. Croatian reply + five probes    probes DONE offline; the reply is a
                                       CORRECTION and is blocked on the loop
    2. proactive client updates        half built, checkpointed, §4
    3. weekly client report            not started
    4. positive replies to the client  not started. Its precondition IS met:
                                       the production session confirmed the
                                       classifier re-run in its overnight
                                       handoff §5 - 0 positive of 14. So the
                                       path can be built; it will post nothing
                                       until a positive appears, which is the
                                       correct behaviour and not a bug.
    5. question catalogue, next ten    not started
    6. multi-workspace readiness       not started. NOTE: #mediaboard-resonate-
                                       outbound and #nextoria-team already
                                       exist - a synthetic second client may
                                       not be needed, but binding a real one is
                                       an operator decision, not this session's.
    7. internal briefing additions     not started
    8. CLIENT-PORTAL-DESIGN.md         not started, and it is last for a reason

---

## 9. THE RULES THIS SESSION WORKED UNDER

Unchanged from the night handoff, stated by the operator and verified for
every commit above:

- Never merges to master and never pushes to it. Delivery is a merge-request
  doc in `docs/` plus one line in `#resonate-os` (`C0C3C6MDN9L`).
- Never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. **Verified**: this session's diff touches
  `src/slackagentreadback.py`, `src/slackagenttools.py`,
  `src/slackfollowup.py`, four test files and two docs. Production's
  `work/workspaces.jsonl` was READ and copied, never written.
- A merge request per increment; a handoff before context runs out.
- Adversarial probes offline only. The five were run with `--ask`, which
  posts nothing.
- **Client mentions are not answered until the loop is on D1/D2 code.** None
  arrived, so none was answered.
