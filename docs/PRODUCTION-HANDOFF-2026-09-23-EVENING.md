# Production handoff - 2026-09-23 evening

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-23-AFTERNOON.md`.**

**STANDING OPERATOR DIRECTIVE: SUPPLY INTO CAMPAIGNS IS THE FIRST JOB**,
above every engineering item except a hard stop, a reply stop or a
client-facing defect. Goal, in the operator's words: the largest sample in
EmailBison and HeyReach we can send safely this week, so learning has data by
Friday.

---

## 1. THE CADENCE FLOOR - OPERATOR DECISION, 2026-09-23 EVENING

Supersedes the earlier "attach steps 4 and 5 to every active campaign"
instruction. The correction is the safe direction.

**From the next NEW campaign onward, including tonight's cohorts:**

- No new Productive email campaign is created or pushed with **fewer than 5
  sequence steps**, waits **3, 4, 5, 7 days**, total ~19 days.
- No lead is pushed into a new campaign unless **body_1 through body_5 are
  all rendered and non-empty**.
- **The existing 3-step campaigns (487, 489, 491-498) stay exactly as they
  are.** Do NOT attach steps. Do NOT backfill. Do NOT touch leads in sequence.
- If step-4/5 copy is not approved, **HOLD new-campaign pushes** and post the
  drafts in #resonate-os.

### Why leaving the existing ones alone matters

All ten active campaigns carry **3 steps at waits 3/4/1, an 8-day span**. 493
was reported as the anomaly; it is not, it is every campaign. No variant is
under test - `variant=False` on all thirty steps. `cadence_version` is
**None** on all ten in `work/campaigns.jsonl`; only `cadence_steps=3` is
stored, so no cadence id was ever stamped.

The provider sequence is a placeholder scaffold, not copy: step 1 is
`{SUBJECT_1}`/`{BODY_1}`, steps 2-3 are `Re: {SUBJECT_1}` with `{BODY_2}`,
`{BODY_3}`. Real copy is injected per lead as custom variables.
`scripts/stage_s7_copy.py` defines `SUBJECT_1`, `BODY_1`, `BODY_2`, `BODY_3`
and nothing else - its header says "3-step, step 1 subject only, steps 2+
thread_reply=true". So 3 steps is not a defect; it is the only shape the
approved words support.

**Measured on a real lead in 491:** `body_1/2/3` hold real sentences;
**`body_4`, `body_5`, `body_6` and `subject_2..subject_6` hold the literal
four-character string `None`** - not empty, so nothing would refuse them.
Attaching steps 4 and 5 to the existing campaigns would have sent two emails
rendering as `None` to roughly 550 real prospects. That is the specific harm
this correction prevents.

`src/cadencelibrary.py` carries an eight-rung ladder (read off the client's
best-performing sequence, 12.23% reply rate at 8 steps, n=17,690) and notes
that EmailBison campaign 481 is staged with nine leads carrying **approved
`subject_5`/`body_5`**. **Look there before drafting new step-5 copy.**

### 1b. The `None` bug - NOT YET FIXED

`bison._variables` is NOT the culprit: it drops empties correctly, since
`str(None or "")` is falsy. `src/bisonfactory.py` lines 1255-1258 and
1307-1310 use `or ""` correctly too. **The site that produced the literal
string has not been found.** It is upstream of both.

Operator asked for, none of it written yet: `str(None)` never reaches a
provider variable; missing means empty string; with a test; and **a guard
that refuses a push when any required `BODY_n` is empty**. That guard is also
the enforcement point for the 5-step floor above.

---

## 2. THE CROSS-CHANNEL STOP STILL HAS NOT EXECUTED, AND THE LOOP SAID IT HAD

The controlled test was set up and run today. **It failed, and the failure
looked exactly like success.**

    15:57:01Z  reply matched to the record       contact <the test identity>
    15:57:01Z  record paused locally             reason positive, linkedin
    15:57:01Z  classified                        unknown
               contact.stopped                   null
               membership(491,[204966])          in_sequence at t+0/+10/+20s
    loop log:  REPLY heyreach ingested=3 - the lead is stopped on both channels

*Setup half:* `inbound._stop_at_provider` resolves the campaign through
`_campaign_for(rec)`, which matches `rec["id"]` against each campaign's local
`record_ids` in `work/campaigns.jsonl`. The test record is linked to lead
204966 **at the provider only**; its id is in no campaign's `record_ids`, so
the stop had no campaign to call and did nothing.

*Defect half, and this is the one that matters:* the loop prints "the lead is
stopped on both channels" **unconditionally**. A lead that was never stopped
reports as stopped. Same shape as the original incident, on the safety path.

**Deliberately NOT done:** adding `crosschannel-stop-test-2026-09-23` to
campaign 491's `record_ids`. It would make the stop work and would also put
the test identity into the campaign counts the operator ordered it kept out
of (section 3). Decide the exclusion mechanism first, then link it.

**The LinkedIn halt therefore STANDS.** `scripts/batch_linkedin_push.py` HALT
unchanged. It lifts on a measured sub-15-minute stop both ways.

### Test-lead state

    EmailBison lead 204966   the operator's own address, attached to campaign 491,
                             reads in_sequence
    local record             crosschannel-stop-test-2026-09-23, state=held,
                             contact carries email, the test identity's profile,
                             bison_lead_id 204966
    HeyReach                 campaign 613744, the test identity's profile, state=replied

**Still `in_sequence` in a live campaign and can receive a step.** The
operator's instruction is to remove it and mark it `do_not_contact` once
measured. **NOT done.**

Both writes used route-scoped `allow_writes` with recorded reasons:
`/api/leads` for the create, `/campaigns/491/leads/attach-leads` for the
attach. When reading an attach back use **`membership()`**, the exact
per-lead route; `campaign_lead_ids()` is the aggregate route, serves 15 rows,
and reported this lead absent for minutes after it had in fact attached.

---

## 3. TEST IDENTITY EXCLUDED PERMANENTLY - AND BRUNO REPLIED BY HAND

The LinkedIn replies in 613744 (14:34, 16:16, 17:54) are **the operator's own
test**. the test identity's profile and lead 204966 are excluded from **every reply count,
report and client figure, now and permanently.**

**Done:** one notification existed - a `positive_reply` planned to
**`C0BFUF4JRK9`, Productive's own channel** - now `suppressed`, channel
`None`. The client did not receive it.

**Not done:** no permanent mechanism exists. A constant naming the test
identity, consulted where replies are counted (`slackagenttools.py:2289`
builds `positive_replies_our_classifier` from `notify.history`) and where the
notification is written, still has to be built. **Until then every new reply
from that profile plans another notification to the client's channel.**

### The finding that outranks it

**A Productive seat holder answered manually at 16:10 from the seat inbox.** Productive's
own seat holders reply on LinkedIn themselves, in the same threads, so an
automated reply can collide mid-conversation with a human one at the client.
**The reply-ownership policy must be settled with Productive before the reply
engine sends anything under their names.** This is a stronger reason for
`SENDING_ENABLED = False` than the one recorded beside the flag, and it
should be quoted there.

---

## 4. WHY THE AGENT "ANSWERS ONLY THE OPERATOR"

Colleagues reported this. **The requested per-message table cannot be
produced, because no such events exist.** `work/slack-agent.jsonl` holds 56
rows since 2026-09-21 and exactly two user values: the operator U07KWV94J0H
(48) and `None` (8). **Zero inbound from any other human, ever.** Reading
#resonate-os back confirms it: the only human posting is the operator, and
U0ASV6PP8P4 is Claude - other sessions posting their reports.

Four mechanisms, all measured, any of which produces the symptom:

1. **The agent listens in three channels only** - internal `C0C34GCAR27` and
   `C0C3C6MDN9L`, client `C0ADUMGQX8S` (gagged). Anywhere else it is absent.
2. **In a channel it answers only @-mentions.** In the last 40 messages of
   #resonate-os there is exactly ONE bot mention, and it is the operator's.
3. **A DM resolves by USER, not channel** (`slackscope.resolve`,
   `channel_type == "im"`). `internal_users` currently holds FOUR ids:
   U0BLHK5U0AX, U09UV3LDW0Y, U07KWV94J0H, U0AFFQ7CA8Y. **Anyone else DMing
   resolves UNBOUND** - "dm: unknown user" - and gets the unbound fallback.
4. **The agent was deaf for most of today.** Down 05:29Z to ~12:05Z, and it
   has handled **zero envelopes since 11:51:49Z**: heartbeat at 15:02:26Z
   reads `last_envelope: "hello"`, `answered: 28`, unchanged. Socket Mode
   does not replay missed messages, so anything sent in those windows is
   permanently lost - which looks exactly like being ignored.

**To fix (3) the next session needs the Slack user ids of the Resonate team
members to add.** Adding someone to internal roles grants access to internal
client data, so it is a permission decision and the ids must come from the
operator.

The liveness trap from the afternoon handoff is live right now: the agent's
heartbeat only advances when it handles an envelope, so `--status` will call
slack-agent DOWN while the process is alive and connected. Check the process
and the socket, not the beat alone.

---

## 5. SUPPLY PIPELINE - WHERE IT ACTUALLY IS

### The 2026-09-07 file, re-judged under both amendments

    verdict     baseline   amended     delta
    in             5,094    19,612   +14,518      80.4%
    out           15,642       163   -15,479
    flagged        3,668     4,629      +961

Diffed as SETS: all 5,094 baseline IN kept, 14,518 recovered, **zero lost**.
Re-judged OFFLINE at zero credits - the journal already carried
employees/country/industry, every field the judge reads. Baseline journal
untouched; the amended one is
`work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl`.

Two operator amendments, both bound to this snapshot, both opt-in, both
carrying the operator's name and date in the code:

1. **Headcount removed** - `judge(..., headcount=False)`.
2. **Client-supplied geo** - `client_supplied=True`: a client-supplied domain
   is IN even outside the allow list; the block list still returns OUT.
   **A separate parameter on purpose** - SOURCED supply from Canada, Poland
   or Czechia stays FLAGGED pending Productive's answer.

`config/clients/productive.yaml` was permanently aligned to the client's
structural criteria: **17 geos** (was 8, narrower than Productive's own ICP
and the real reason the file read 65.3%), `exclude_geos` widened 3 to 16.
Both copies changed - `market.geos` AND `icp.markets`, which that file's own
comment warns are read by different code paths.

### MX - DONE

`scripts/stage_mx_amended.py`, DNS only, no credits. **Email channel open on
23,363 of 24,181.** `known_blocked` 616, `no_mx` 159, `dns_failure` 43.
Journal `work/stage/mx-amended-PRODUCTIVE-2026-09-07.jsonl`.

### Collision - RAN, BUT ON THE WRONG SUPPLY

    S6 COLLISION WALK  3,080 accounts answered
      stop / in_sequence  1198        allow / clear    577
      hold / touched       714        allow / touched  223
      stop / touched       357        REFUSED           10
      CLEAR accounts: 800

**It walked `work/_s/supply.json`, batch 3's domain set, NOT the 19,612
amended IN set.** `s6_collision_walk.targets()` reads that file and nothing
else. A fresh walk against the amended supply is required before any 09-07
cohort can be pushed. Its `--report` path also crashed with
`NameError: clear`; fixed today, one line.

### S5, S7 - NOT STARTED on this supply

`stage_s5_verify.py` reads `S3 = work/stage/s3-icp.jsonl`, the **baseline**
journal, and gates on `row["mx"] in MX_OK`. It therefore ignores the amended
set entirely. It needs an `--s3` argument pointed at the amended + MX
journal. **Not yet added.**

---

## 6. FORWARD BOOK: THE SHORTCUT IS DEAD, THE PUSH IS NOT BLOCKED

**`sending_schedules` cannot replace the census.** Measured against our
instance: the plural and singular routes BOTH return
`{campaign_id, emails_being_sent}` and nothing else - no sender, no mailbox,
no breakdown - and only three day tokens exist. A campaign-level total cannot
answer a per-MAILBOX question when the cap is per mailbox and mailboxes are
shared across campaigns.

**What replaces it for TODAY only:** `scripts/bison_room_today.py`.
`emails_sent_count` is a lifetime counter; diffed against a pre-midnight
sample, `room = daily_limit - sent_today` is exact per mailbox at zero page
cost. A mailbox with no baseline sample is UNKNOWN and never counted as room.

    raw room today                2,837 slots, 220 mailboxes, 5 FULL
    scheduled today               1,206  (ours 200, client 1,006)
    scheduled tomorrow              937  (ours  29, client   908)
    scheduled day after           1,437  (ours 480, client   957)
    estate capacity               3,415  (3,160 Connected)

    GENUINE FREE ROOM TODAY   ~1,954 slots

The raw 2,837 **OVERCOUNTS** - it measures what mailboxes have sent, not what
is already queued. Use ~1,954. The census's "free slots 0" came from a 40.3h
stale walk where 95 mailboxes were REFUSED; **refused is not room, and it is
not "no room" either.** The client's own campaigns consume most of the
scheduled load, so the room is real but shared - size conservatively.

For any day past `day_after_tomorrow` only the 12,438-page census
(`bison_forward_book_census.py --reset`, 1.7-5.2h) can answer. It shares a
rate limit with the 90k walk; sequence them.

---

## 7. WHAT MERGED AND DEPLOYED TODAY

    bbc5df69  infra, 100 commits. TASK-251..265, scripts/cold_start.py,
              src/supervisor.py, src/seatledger.py, test isolation, a
              766-line src/store.py rework. QUEUE_BACKEND defaults to jsonl
              and is NOT set in config/.env, so the store behaves as before.
    9788ce2e  slack-agent, 14 commits. D3, D4, accounts-first.
    c382fcab  headcount amendment + 8 tests
    e1f93730  geo decisions, config alignment, bison_room_today
    2ad8b907  HUMAN-ACTIONS-REQUIRED rewritten to current truth

**Known regression merged deliberately and recorded:**
`test_e2e.TestTheProviderWaterfall` - two deliverability guards pass on
master and FAIL at the infra tip. `src/providers/deliverable.py` is
byte-identical between the branches, so it is the e2e runner's env load
escaping the isolation harness, not a production hole. It guards a named,
previously-reverted incident (the gate opening itself, reverted 2026-09-16).

**Deploy state.** `slack-agent` (32072) and `slack-followup` (39440)
restarted 17:02; `replies` (32168) restarted 17:13. All module mtimes precede
all three starts. **The other nine loops still run pre-merge code** and pick
up the new `store.py` on their next restart - tonight's controlled reboot.

`slack-followup` was NOT in `MONITORS` and was NOT running; it is now in the
table. `slackfollowup.deliverer_is_running()` reads its heartbeat to decide
whether the agent may make the follow-up offer at all, so an absent loop was
not the same as a quiet one.

**12 UP** at handoff.

---

## 8. WHAT NEEDS THE OPERATOR

Current truth is at the TOP of `HUMAN-ACTIONS-REQUIRED.md`, rewritten today.
Two entries there were false and are corrected with measurements: Deliverable
reads BLOCKING when `DELIVERABLE_RESULT_SHAPE=confirmed` has been set since
2026-09-22 13:03, and the LinkedIn connection request is listed as waiting
when the test identity's profile is `state=replied` since 2026-09-23T10:58:13Z.

1. **Approve steps 4-5 copy** - new-campaign pushes are HELD until then.
2. **Reply-ownership policy with Productive** (section 3).
3. **Slack user ids of the Resonate team members** to add to internal roles
   (section 4).
4. `prompts/reply_handling.md`.
5. Approve or reject the 32,951 QUALIFIED.
6. Canada / Poland / Czechia for SOURCED supply - the question to Productive.
7. ISSUE-012 slice subdivision: a spend decision.
8. Record the re-engagement approval artifact, or say the verbatim quote
   suffices.
9. Auto-logon (ARSO) decision and the reboot test.

---

## 9. STILL NOT STARTED

rules-4 (`replies.VERSION` is still `rules-3`), ledger write-back of provider
events, the four gag-lift items, supervisor adoption, the controlled reboot
with `cold_start --verify`, the AU ninth campaign, the 289 re-engagement
leads, the 985 re-engagement wave, the 48,017 export sample, the geo
resolution chain for the 4,629 no-country domains (TLD -> free crawl ->
AI-ARK, in that order, reporting how many resolve and where they land), the
2,519 no-company FLAGGED, the workforce restructure and
`docs/ACCOUNT-BASED-DESIGN.md`.

The 90k walk (pid 27288) begins on its own at 21:00Z and **is not in
`start_monitors`**, so a reboot kills it with nothing to bring it back. It is
resumable.

---

## 10. THE PATTERN, AGAIN

Two more today, both found by asking what the failure would look like and
noticing it looked like the success:

    a stop that never ran        the loop printed "stopped on both channels"
    copy that does not exist     the slots hold the STRING None, not empty

And one correction worth carrying: **a committed baseline JSON is a claim,
not a measurement.** `SUITE-BASELINE-2026-09-23.json` on `infra` listed the
ContactOut allowlist test as failing; the branch TIP is the commit that fixes
it. Run the test at the tip before reporting a regression from a file.
