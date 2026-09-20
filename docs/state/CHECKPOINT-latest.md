# Autonomous run checkpoint - 2026-09-20, 19:20 UTC

Supersedes the 2026-09-16 checkpoint, which was four days stale and described
a production state that has since changed in every material respect. Written
by Claude after a session-limit context reset, with every number recomputed
rather than carried forward.

**READ THE CLOCK FIRST.** This was written on SUNDAY 2026-09-20. Both email
campaigns are Mon-Fri. A zero at a weekend is the calendar, not a fault.

---

## GIT

    master HEAD     42eb425a
    origin/master   42eb425a   identical, verified
    today           4 units integrated and pushed

---

## P0 - THE ONE THING THAT MATTERS ON MONDAY

**Campaign 487 is PAUSED and its recovery is armed, unrun, and belongs to
the operator.**

    py -3 scripts/resume_487.py --live      MONDAY 2026-09-21, from 07:00Z

`docs/OPERATOR-AUTHORIZATION-2026-09-20-RESUME-487.md` is the standing grant
and a fresh session may act on it without re-asking. The operator's own
decision was **"You run it Monday morning"**, so nothing is scheduled and no
session fires it. If nobody types the command, the recovery does not happen.

Preflight re-run 2026-09-20T19:11Z - **every condition except the window is
MET**:

    window      LATER   opens 2026-09-21T07:00Z
    truth       PASS    campaign 'paused', 10 leads, senders [2736]
    membership  PASS    {'sending_paused': 10}
    copy        PASS    10 of 10 queued rows carry the approved text

Success is `in_sequence` on all ten leads. Campaign `active` with leads still
`sending_paused` is the SAME FAULT, and condition 5 is ONCE - do not retry.

---

## PRODUCTION TRUTH, read from the providers today

    EmailBison 487   paused   10 leads  0 sent  first scheduled 09-22T07:39Z
    EmailBison 489   active    5 leads  0 sent  first scheduled 09-24T13:27Z
    HeyReach 605732  IN_PROGRESS 3 leads        (of 86 campaigns in the
                                                 account, 4 are ours)

    enrollments      15 email + 3 LinkedIn = 18
    provider-confirmed sends                    0 on both channels
    cross-channel overlap of those 18           UNVERIFIED - do not report a
                                                unique figure until measured

Nothing has sent from these three. The proven end-to-end path is canary 451,
one real email on 2026-09-14.

**Gap to the 500-lead target is therefore ~482, and the limiting stage is
company enrichment** - see the 215 section. It is not approval, not copy, not
sender capacity and not provider execution.

The READY reservoir is **depth 0 on both channels** and is itself stale
(generated 09-18):

    linkedin  population 81   blockers: approval 66, copy 9, collision 3
    email     population 51   blockers: approval 36, collision 15

---

## A P0 REGRESSION FOUND AND FIXED TODAY

**The write guard refused every HeyReach READ.** HeyReach answers its reads
with POST, the guard is method-based, and from 17:04 on 2026-09-20 every
`/campaign/GetAll`, `/campaign/GetLeadsFromCampaign`, `/stats/GetOverallStats`
and `/inbox/GetConversationsV2` raised `ProviderWriteRefused`.

It was invisible for a day **because nothing already running had to
re-import**. The 605732 watcher started at 14:23 and the guard landed at
17:04, so it holds the pre-guard module in memory and has been reporting
healthy heartbeats throughout. It would have died on restart, and 605732 is
the only live LinkedIn campaign. `provider_truth.py`, started fresh, crashed
on its first call - which is how it was found.

Fixed in `28f4766e`: a prospect-facing module may declare the paths where
POST is a READ, via `guard_read_routes`, at import. Only POST is exempt, the
match is exact on the parsed path, and a test pins that the declared reads
and `WRITE_ROUTES` stay disjoint. The incident verb - `PATCH .../487/pause` -
is still refused, with its own regression test. Verified by disabling the
exemption and confirming all 13 new tests fail as `ProviderWriteRefused`
rather than something else firing first. `provider_truth.py` then completed
live against all four Resonate HeyReach campaigns.

**The running watchers were deliberately left alone** - they are healthy, and
the fix means a future restart now works.

---

## THE 215, SETTLED

`docs/THE-215-WERE-NEVER-JUDGED-2026-09-20.md` is the full account.

**Zero of the 215 have failed a single criterion.** None carries a contact.
All 215 are still `queued`. 208 are blocked on geography, and 184 hold no
company evidence beyond a headcount signal. They are not a rejected backlog
and they are not waiting on a human verdict - **remove "215 records await a
human ICP verdict" from the operator's list. It is and always was an
enrichment task.**

The ISO-code fix for `geo.resolve` is **already on master** (`27bcdb67`,
2026-09-17) - an earlier version of this checkpoint wrongly called it
stranded. The 215's verdicts are STALE, computed 2026-09-12, five days
before it landed. Re-qualifying all 215 against current master through the
real `icp.score` path moves geography from 7 pass to 8 and yields **exactly
ONE newly qualified record.** Worth running; not expansion. What IS still
unintegrated on that branch is TASK-227's cohort send-window work.

Next step before any batch: a bounded measurement of verdict movement per
credit over the 71 one-field-away records. The 09-16 result that ContactOut
company-info moved ZERO verdicts over 50 records stands against the obvious
provider choice.

---

## WORKFORCE - verified by execution, not by configuration

    CLAUDE   RUNNING   this session
    PYTHON   RUNNING   5 monitors live, all heartbeating within 90s
    GLM      IDLE      glm-5.3 via ZAI_API_KEY verified live, 200 in 1840ms.
                       LAST TASK FAILED: empty completion,
                       finish_reason='length' on both targets. Truncation,
                       not auth. Needs a smaller target or a higher cap.
    GROK     IDLE      grok-4.6 via XAI_API_KEY verified live, 200.
                       Last run SUCCEEDED 17:41 (120 + 68 sources).
    QWEN     IDLE      CLI v0.23.3 present. 8 worktrees, 0 claims, 0 locks.
                       Pool has not dispatched since 2026-09-16 15:42 (r50).

**Qwen is idle because the backlog is starved, not because it is broken.**
`claim_task.py --status` reports **2 ready tasks for 8 workers** against a
healthy threshold of 16, and **89 stale branches hiding available tasks**.

`ZAI_API_KEY` and `XAI_API_KEY` are **NOT in `config.VARIABLES`**, so
`credential_health.py` structurally cannot report on the two model workers.
That is the honest failure mode by design, and it is a registry gap worth
closing.

### 11 finished tasks are sitting unintegrated on branches

From `scripts/task173_scan.py --unintegrated`. This is the single largest
pool of recoverable value in the system:

    TASK-067  origin/qwen-worker-7
    TASK-212  origin/qwen-worker-3-r45
    TASK-213  origin/qwen-worker-4-r45
    TASK-214  origin/qwen-worker-r45
    TASK-225  origin/qwen-worker-7-r28
    TASK-227  origin/geo-iso-resolution-2026-09-17   (cohort send window;
              its ISO fix is ALREADY on master as 27bcdb67)
    TASK-229  origin/bounded-gather-2026-09-18
    TASK-230  origin/task-230-prefetch-headcount
    TASK-231  origin/qwen-worker-8-r28
    TASK-232  origin/qwen-worker-6-r40
    TASK-234  origin/task-234-stop-button

Integrating these also clears the stale-branch noise that is hiding ready
work from the dispatcher, so it unblocks Qwen as a side effect.

---

## SLACK - the adapter works, the credential does not exist

    SLACK_BOT_TOKEN        NOT SET
    SLACK_SIGNING_SECRET   NOT SET
    SLACK_OPS_CHANNEL      NOT SET
    SLACK_LIVE             NOT SET

`src/providers/slack.py` and `src/notify.py` both exist and **the
notification layer is working**: it has produced 216 notifications, of which
**207 are `unconfigured` - recorded and delivered to nobody.** The reason is
stated on every row: *"no global operations channel is configured; set
SLACK_OPS_CHANNEL"*.

**The operational consequence is the thing to understand: there is no
delivered alerting at all.** A positive reply on a live campaign tomorrow
would be written to `work/notifications.jsonl` and told to no one. 203 of the
undelivered rows are `unmatched_reply_needs_review` at severity
`action_required`, still arriving (last 2026-09-20T18:01Z) - HeyReach inbox
conversations the watcher cannot map to our leads, which is expected given we
own 4 of 86 campaigns in that account, but a real reply lands in the same
silent bucket.

The 5 `positive_reply` rows are all dated 2026-08-28 across `demo`,
`demo-client`, `contactout` and `productive` in one batch - fixtures from
when the layer was built, not live business signal. Checked rather than
raised as an alarm.

**For outbound notification only, a bot token plus `SLACK_OPS_CHANNEL` plus
`SLACK_LIVE` is sufficient - no incoming webhook and no Events API are
required.** Those are only needed to read messages or accept commands, and
Slack-based production approvals must not be built until identity,
authorization, auditability and replay protection are designed.

---

## INTEGRATION HEALTH, verified live today

    CONTACTOUT_TOKEN  AUTHENTICATION_VERIFIED   963ms
    BLITZ_API_KEY     AUTHENTICATION_VERIFIED   444ms
    AIARK_KEY         AUTHENTICATION_VERIFIED   545ms   11 tools
    BISON_KEY         AUTHENTICATION_VERIFIED   204ms   15 campaigns
    HEYREACH_KEY      AUTHENTICATION_VERIFIED   113ms
    ZAI_API_KEY       AUTHENTICATION_VERIFIED  1840ms   glm-5.3
    XAI_API_KEY       AUTHENTICATION_VERIFIED           grok-4.6
    APIFY_TOKEN       CONFIGURED_UNVERIFIED
    LLM_API_KEY       CONFIGURED_UNVERIFIED
    REOON_KEY         PROVIDER_UNAVAILABLE  the only endpoint costs a credit
    DELIVERABLE_KEY   PROVIDER_UNAVAILABLE  no account or quota endpoint
    SLACK_BOT_TOKEN   NOT_CONFIGURED

ContactOut month to date: 1,553 of 38,232 credits used, 396 of 117,815
searches. Roughly 36,700 credits remain. **Enrichment is not credit-limited.**

---

## TEST BASELINE - three failures that are NOT new

`work/suite-2026-09-20-failures.txt` is the baseline. Confirmed today by
stashing the day's changes and re-running: identical with and without them.

    test_fixture_hygiene   3 failures  (the PII guard is RED, and was
                                        reported green on 09-16)
    test_red_team_tonights_guards  3 failures (fatigue hold)

The PII guard being red is a real open item, not a nuisance - it is the
control that catches a worker committing a prospect name.

---

## NEXT ACTIONS, in order of what unblocks most

1. **MONDAY 07:00Z: the operator runs `scripts/resume_487.py --live`.**
   Nothing else on this list produces a real send this week.
2. **Integrate the 11 branch-finished tasks.** Their stale branches are what
   hide ready work from the dispatcher, so this unblocks Qwen as a side
   effect. Note TASK-227's branch conflicts on
   `scripts/task_geo_iso_coverage.py`, which master already has.
3. **Refill the task backlog** - 2 ready for 8 workers. Qwen cannot work
   without briefs.
4. **Set `SLACK_BOT_TOKEN`, `SLACK_OPS_CHANNEL`, `SLACK_LIVE`.** Operator
   action. Until then the system has no way to tell anybody anything.
5. **Re-qualify the estate** to clear verdicts predating the 09-17 geo fix
   (yields 1 lead, measured), then **measure verdict movement per credit**
   over the 71 one-field-away records before spending on the 215.
6. **Add `ZAI_API_KEY` and `XAI_API_KEY` to `config.VARIABLES`** so the two
   model workers are visible to `credential_health.py`.
7. **Give GLM a smaller target.** Its last run truncated on both.
