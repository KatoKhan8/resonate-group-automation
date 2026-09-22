# Production handoff — 2026-09-22 afternoon

Written for a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-22-MORNING.md`**, whose headline — both
channels live, 151 leads enrolled, nothing sent — is superseded on every count.

---

## 1. THE HEADLINE: THE BATCH ARCHITECTURE HAS SENT

**2026-09-22T13:02:46Z, campaign 495.** The first provider-confirmed send from
the batch architecture, on three independent witnesses: the campaign counter
0→1 at 13:02:49Z, scheduled row `22347302` reading `sent` with `sent_at`
13:02:46Z against `scheduled_date` 13:02:00Z, and the watcher reporting SEND on
both the counter AND the queue row, which are its two deliberately separate
witnesses.

489 sent three real emails yesterday. Those were a five-lead cohort on one
mailbox. This is eight campaigns, one per attested human, 154 attested
mailboxes, a cohort per timezone, per-lead rendered copy, and a forward book
choosing which mailbox is free on which day. Every layer had to be right for
that row to flip.

State at 14:01Z, read from the provider rather than inferred:

    camp  human      leads  rows  sent  first scheduled
    491   kresimir     330   585     4  2026-09-22T13:03Z
    492   bernarda     206   339    14  2026-09-22T13:16Z
    493   ivan          22    22     0  2026-09-24T13:20Z
    494   fran          76   145     6  2026-09-22T13:06Z
    495   tomislav      60   100     1  2026-09-22T13:02Z
    496   bojan          9     9     0  2026-09-24T08:10Z
    497   jakov          7     7     0  2026-09-24T08:33Z
    498   luka          13    13     0  2026-09-24T07:09Z
    --------------------------------------------------
                       723  1220    25

**0 bounced · 0 replied · 0 unsubscribed**, on counters and per-row reads
alike. 33 HeyReach campaigns IN_PROGRESS with connectionsSent still 0 on every
one.

**ENROLLED IS NOT SENT. SENT IS NOT DELIVERED.** 25 accepted sends is not an
inbox placement, and 1,195 rows are still `scheduled`.

## 2. BATCH 3 IS COMPLETE, AND THREE GUARDS HAD TO BE FIXED TO LAND IT

572 leads enrolled today on top of the morning's 151. Every refusal along the
way was a guard being imprecise, never a bad lead getting through, and none was
weakened to let the batch pass.

**ISSUE-014** — an ACTIVATED campaign collided with itself. Our own membership
made every account it held read `in_sequence`, so a standing campaign could
never be topped up and the CONTINUOUS grant was unsatisfiable. 95 of 95
accounts read STOP with ZERO client-side live sequences among them.

**ISSUE-018** — that fix required the campaign to be SILENT, so the first send
locked it against every remaining lead. The premise, "a row reading zero may
lag", was measured and is FALSE here: 17 minutes after 495's send, the lead it
sent to read `emails_sent 1` on its own row while another lead at the same
account read 0. Per-lead counters update and discriminate.

**ISSUE-021** — `stage` re-submits every lead, so a lead WE emailed collided
with its own sent state and refused the WHOLE stage; two contacted people
blocked 34 good ones. A lead already on the campaign is being re-described, not
added.

All three fixed with tests that name them. **The pattern to carry forward: each
was found by doing the work, and each fix narrowed the guard to the defect
rather than widening it past the defect.**

## 3. WHAT IS WAITING ON THE OPERATOR

1. **ISSUE-019, CRITICAL. The candidate export is STOPPED and nothing was sent
   to Productive.** `_icp_verdict` passes ICP REVIEW as though it were IN, so
   1,508 candidates have median headcount 16,745, none under 20 staff, and
   include a 130,377-employee bank at `icp_score 0.0` and a national education
   ministry. The operator has since ruled: QUALIFIED only, REVIEW goes to
   enrichment and a later export. **NOT YET IMPLEMENTED.**
2. **AI ARK CANNOT SLICE, AND IT BLOCKS THE EXPORT STRATEGY.**
   `companyIndustry` and `companyLocation` are ACCEPTED AND INERT — proved by
   comparing filtered with unfiltered pages: identical `totalElements`
   (72,657,969), byte-identical row hashes, same first rows across all four
   filter combinations. The operator's country × industry × headcount slicing
   cannot partition anything. `people_search` DOES filter — 302,653 results for
   UK advertising with real agency people — so the route to the ICP is probably
   people-first. **Unverified; do not build on it without measuring.**
3. **The ninth campaign for Australia is AUTHORIZED** (grant amended 8→9,
   recorded verbatim in the batch-1 authorization) and NOT YET BUILT. 694 of
   the 985 re-engagement leads are Australian with nowhere to send from.
4. **Re-engagement copy is APPROVED** — ticket `2026-09-22-d21e`, pullable with
   `slack_requests.py --approved` — and the batch is NOT YET BUILT. 289 US
   leads are the actionable half.
5. **37 REVIVE leads** — no enrollment; a drafted next message per thread to
   `#replies-productive`, 20 a day, a human sends. NOT STARTED. That channel
   has 8 members, all Resonate-side: 5 humans, the Resonate OS bot, and the
   `clickup` and `heyreach_ai_agent` apps. No external Productive user is in
   it, so prospect drafts there are internal-only.

## 4. THE LEARNING WALK, AND ITS FIRST NUMBER

`scripts/learning_walk_replies.py` walks every reply in the estate. Resumable,
cursor-paginated, stores no message bodies — only campaign, lead, domain,
timestamp, `interested` and `automated`. At ~3,750 rows over 250 pages, cursor
at 2026-04-04, NOT complete.

**Of the first 2,700: 1,747 were AUTOMATED and 18 marked interested.** If that
holds it reframes what "reply rate" has ever meant in this estate. The
operator's instruction: that finding leads
`LEARNING-FROM-HISTORY-PRODUCTIVE.md` with full-history numbers once the walk
completes, and **"automated vs human reply" becomes a standing split in every
reply count reported, internal and client.**

The send-side denominator — subject, step, sender, hour, weekday per send — is
a walk of ~186,000 scheduled-email rows across 327/328/352 and has NOT started.

## 5. WHAT MUST NOT BE RE-DERIVED

- **The PII guard is `tests/test_fixture_hygiene.py`, 13 tests, and it went red
  twice.** ISSUE-006 is REOPENED: a red guard was closed as "catches nothing"
  while it was catching real prospect addresses. Four of today's leaks came
  from writing evidence INTO the register. Evidence can be named without being
  identifying: `<prospect-a>@example.test`, `<account-c>.example.test`.
- **The re-engagement lane is NOT a stored value** (ISSUE-017). It is derived
  from campaign status and goes stale when a campaign archives. Read it with
  `lanes_now()`, never the stored `lane` field. Trusting that field is how this
  session reported an existing 985-lead supply as missing.
- **The store's atomic write loses to a concurrent reader on Windows**
  (ISSUE-022). Eleven processes read `work/` continuously; a push can fail with
  WinError 5. The OLD file survives and the caller reports REFUSED, so retry.
  Three stale `*.tmp` files in `work/` are litter, not state.
- **`claim_task.py --next` CLAIMS, it does not query.**
- **The Qwen pool is short of READY WORK, not workers.** `pool.sh sweep` is one
  round, not a daemon. `claim_task --status` reports ready 0 against **90 stale
  branches** hiding available tasks. Restarting it again changes nothing;
  pruning those branches would.
- **AI Ark lookups answer under the PLURAL key** (`locations`, `industries`,
  `technologies`). Every enum lookup returned `[]` before today, which made
  every enum-filtered search in the estate unreachable.
- **`stage_s7_copy` TRUNCATES its journal.** It now keeps a stamped backup
  first; before that it silently replaced the 871 rows batch 1 and 2 were built
  from.

## 6. MONITORS

    86848  bison_mailbox_utilisation   19236  reply_watch_loop
    95760  notify_deliver_loop         89640  bison_watch_loop 487
    105276 bison_watch_loop 489        92332  heyreach_watch_loop
    110384 digest_loop                 116292 slack_agent_loop
    121496 bison_watch_loop 491        38316  bison_watch_loop 492
    120392 bison_watch_loop 494        120324 bison_watch_loop 495

All alive on fresh heartbeats. Restart bare, **never under `timeout`**.

**The slack agent's heartbeat beats on every Slack ENVELOPE, not on a timer**,
so it cannot tell quiet from hung — which is how a four-hour hang stayed
invisible this morning. Nothing watches it.

**Exactly one watcher per campaign.** The process list shows a `nohup.exe` and
a `py.exe` wrapper beside each real `python.exe`; counting those as duplicates
is how this session briefly killed all four watchers seconds before a send
window. Filter on `Name -eq python.exe`.

## 7. THE THREE-SESSION RULE

Production on master, slack-agent worktree, infra worktree. Only production
commits to master and merges; the others deliver via merge-request docs.
Nobody but production edits `config/.env`, `src/providers/*`,
`scripts/*_watch_loop.py` or anything under `work/`.

Merged today: slack-agent Phase C1+C2 (`cd143eda`), infra's five
(`d88d08db`). **Check a branch against its MERGE BASE, never against master's
tip** — the two-point diff showed Phase C deleting four test files it does not
touch, which is the TASK-229 trap CLAUDE.md records.
