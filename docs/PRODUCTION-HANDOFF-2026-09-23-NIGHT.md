# Production handoff — 2026-09-23 night

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-23-EVENING.md`.**

Standing directive unchanged: **supply into campaigns is the first job**,
above every engineering item except a hard stop, a reply stop or a
client-facing defect. Tonight produced a client-facing defect, and it took
priority correctly.

Two new standing directives arrived this evening and are recorded in
`docs/OPERATOR-DIRECTIVES-2026-09-23-EVENING.md`: the **research pack**
between S5 and S7, and **copy quality as a first-class job**. Neither is
started. One instruction in them arrived truncated — see that file, §A5.

---

## 1. THE BLANK EMAILS — 76 SENT, 77 STOPPED, CONTAINED

**Found by reading what the PROVIDER RECORDS AS SENT, not our render.** That
distinction is the whole finding: every local check said the copy was fine.

    step 4769, campaign 497, verbatim from the provider:
        subject = ''
        body    = '<p></p>'

Five prospects in 497 received a completely blank email today (08:31, 09:02,
13:15, 14:28, 14:30 UTC). **`<prospect-a>@example.test` REPLIED to
his** — his membership reads `replied`. A prospect answered an empty message
from us.

Swept all ten campaigns against provider-recorded content:

    campaign   sent blank   was queued blank
    491            42            42
    492            21            20
    494             7             7
    495             1             0
    496             0             6
    497             5             4
    498             0             2
    ----------------------------------------
    total          76            77

487, 489 and 493 are clean.

**77 leads stopped.** Before stopping, each was checked for a *good* step
still to come: **`also-has-good-step = 0` in every campaign** — every
remaining step for every one of these leads was blank. Stopping forfeited no
real outreach. 63 of the 77 had already received a blank. Re-read
independently afterwards: **0 blank rows still scheduled across 487–498.**

**THIS IS NOT THE LITERAL-`None` BUG.** The evening handoff records
`body_4/5/6` holding the four-character string `None` on a 491 lead. What
actually sent is genuinely EMPTY. Two faults, one cause upstream, and the
empty one is the one that reached people. The guard as specified — refuse a
push where a required `BODY_n` is empty **or** `"None"` — catches both. **It
is still not written.** This is what that cost.

Artifacts: `work/blank-body-sweep-2026-09-23.json`,
`work/blank-body-leads-2026-09-23.json`.

### The account rule, applied

Operator instruction: one NEW person per account per week, the rest deferred.
Applied to every remaining queue. 40 domains have more than one person
scheduled, but **only 4 are genuinely NEW** — the rest are follow-up steps to
people already mid-sequence, which the rule does not touch. Those 4 were
stopped (`work/account-rule-defer-2026-09-23.json`). Deferred means *not this
week*; they can be enrolled in a later batch.

**Why four contacts at one account landed in one campaign on one day is
NOT yet answered.** They are all stopped now, so nothing is pending on it,
but the sourcing/staging path that let four people at one account into one
cohort has not been traced.

---

## 2. THE CROSS-CHANNEL STOP — ONE DIRECTION MEASURED, ONE STRUCTURALLY ABSENT

**LinkedIn → email: PASSED at 7.7 minutes**, the operator's 18:59 reply:

    16:59:43Z  reply created at HeyReach
    ~17:04:08Z visible in the inbox feed          +4.4 min
    17:07:18Z  reply seen (ingested)              +7.6 min
    17:07:22Z  classified `unknown`, rules-3      +7.7 min
    17:07:27Z  PROVIDER STOP CONFIRMED            +7.7 min

Two witnesses: the loop's derived line `email: stopped; linkedin: no lead`
with zero refusals, and an independent `membership(491,[204967])` reading
`stopped` (was `in_sequence`).

**4.4 of the 7.7 minutes were provider visibility** — before any of our code
could run. We control ~3.3 minutes of the 15-minute budget.

An `unknown` classification still stopped the sequence, which is the
operator's explicit requirement and is now pinned behaviourally.

**Why test #1 failed:** the record was in no campaign's `record_ids`, so
`_campaign_for` returned `None`. Fixed by APPENDING to `record_ids` — the way
`batch1_build.py:941-946` registers a pushed lead. **Not
`orchestrator.set_records`**, which calls `_invalidate_if_needed` and would
have voided a live campaign's approval.

### email → LinkedIn: still NOT measured

`heyreach.stop_lead` was enabled by operator decision (SUPPORTED 14 → 15).
Then two things were found:

1. **`stop_linkedin_contact` read `contact["linkedin_url"]`. No contact has
   ever carried that key** — 1,014 carry `linkedin`, zero carry
   `linkedin_url`. So `profile_url` was always `""`, and
   `heyreach.stop_lead_in_campaign` refuses an empty `leadUrl`. **The
   email→LinkedIn stop could never have succeeded.** Invisible because the
   verb was sealed: `perform` refused before the transport ran. Fixed.
2. **First live exercise of the route: the provider REJECTED the write.**
   Target was the operator's own test profile (the test identity's profile, `Finished`,
   receives nothing either way). Provider truth read immediately after is
   unchanged and no ledger key was left unresolved. The readback conditions
   both pass, so the rejection is at the write; the likeliest reason is that
   a `Finished` lead has no progression to stop. **THE ROUTE REMAINS NOT
   LIVE-VALIDATED.**

### THE LINKEDIN HALT STANDS, and there is a third reason now

    0 contacts are bound on BOTH providers (756 email-only)
    0 records are in both an email and a LinkedIn campaign row
    0 campaign rows carry both a bison_campaign_id and a heyreach_campaign_id

`leadstop._campaign_of` returns the FIRST row holding a record. **The day a
record is in both, one of the two directions resolves the wrong provider
campaign or refuses.** That is the day the 33 seats are enrolled.
`tests/test_the_linkedin_stop_can_actually_address_somebody.py` asserts the
population is empty and fails with that instruction the moment it is not.

**Do not enrol the 33 seats until email→LinkedIn is measured.** Enrolling
with one direction working means a prospect who says no by email keeps
receiving LinkedIn messages.

---

## 3. WHAT THE WATCHER NOW SAYS, AND WHAT IT USED TO CLAIM

`reply_watch_loop` printed **"the lead is stopped on both channels" as a
constant**, on any non-zero ingest, consulting nothing. It said that twice
about leads that were never stopped. It now reports per channel — stopped /
already stopped / REFUSED with the reason / no lead — built from
`inbound.summarise_stops`. A refusal raises `REPLY_PROTECTION_FAILED`
(GLOBAL, CRITICAL) to `#resonate-notifications`.

**Both channels are now attempted from the reply path.** Only the EmailBison
half ever was, while `STOP_ROUTES` authorised the HeyReach route the whole
time.

---

## 4. CAMPAIGN 495 ARCHIVED BY SOMEBODY, AND THE API WILL NOT SAY WHO

495 went `active` → `archived` at 15:57:22Z, 59 of 60 leads `stopped`, 42 of
60 ever contacted, `completion_percentage 100` while every other active
campaign reads 27–37%.

**Not us:** no action-ledger row, no write refusal, our campaign row's last
entry is 09-21, and `hard_stop_check` has **no automated caller**.

**Who is not answerable from the API.** The event feed carries delivery
events only — 6,000 rows, 400 pages, **zero** mentioning an archive — and
neither the campaign row nor the account object names an actor. The one
suggestive number: **bounce rate 2.38% against a 2% estate threshold.**

Now alerted: `CAMPAIGN_STOPPED_EXTERNALLY`, GLOBAL/CRITICAL, its own event
rather than a louder `CAMPAIGN_PAUSED` (which also covers our deliberate
pauses). It reports the transition and whether our own state can account for
it, and **never asserts a third party**. Not un-archived.

**Its first version would have silenced 495.** `_we_did_it` matched any log
NOTE containing "stop", and 495's row carries "0 held by the 2% bounce stop"
from 09-21. Caught by its own test. It now matches the structured `step`
field exactly and only within 6 hours.

---

## 5. THE AGENT IS NOT DEAF — IT WAS A CLOCK

"Zero envelopes since 11:51Z" reconciles: the operator's 13:28 **Zagreb**
mention is the **11:28:37Z** row, answered. The agent went down 13:51 Zagreb,
was restarted 17:02 Zagreb (15:02Z), reads **CONNECTED via Socket Mode**, and
has simply had nothing addressed to it since.

`#resonate-os` is **C0C3C6MDN9L** — already one of its two internal channels.

**Roles are NOT done.** The three Slack ids arrived as literal placeholders
(`<ID_1>`, `<ID_2>`, `<ID_3>`). The operator then superseded that with:
resolve roles from **Slack membership** — non-external members of the
internal channels are Resonate users (DMs included), external members of a
bound client channel are that client's users, everyone else unbound; refresh
on start and hourly; post the resolved internal names once in `#resonate-os`.
**Not started.**

---

## 6. WHAT WAS DEPLOYED, AND THE WATCHER GAP

Restarted onto new code tonight (a merge is not a deploy — these loops import
at start and never reload): `replies`, `notify-deliver`, `bison-491`,
`bison-492`, `bison-494`, `bison-495`. **12 UP.**

**`MONITORS` HOLDS NO WATCHER FOR 496, 497 OR 498.** All three are ACTIVE.
497 is where the blank emails were found — by hand, because nothing was
watching it. `--restart bison-497` fails for that reason. **Add them.**

Also carried from infra, operator's words: adopt **46474c6c or later**, not
the earlier tip — it fixes the monitor-name→heartbeat-file mapping without
which `cold_start --verify` times out. Two findings are ours to fix when
those loops are next touched, **not tonight**: three loops (`notify_deliver`,
`digest`, `slack_agent`) write heartbeats directly instead of through
`watchsink`, and `bison_mailbox_utilisation` never beats at all, so it can
only read `UP_ONE_WITNESS`.

---

## 7. 491 WENT BLIND AND IT WAS A PAGE CAP

`bison-491.json` read `READ-ERROR 122x PartialInventory` for hours while the
campaign answered fine. 491's queue reached 647 rows — 44 pages — past the
40-page default. **The refusal was correct.** Two defects around it:

- a **third reader with a different cap** (`slackagentreadback` and
  `hard_stop_check` both walked 400; the watcher had none). Canonical value
  now at `bison.CAMPAIGN_QUEUE_PAGE_CAP`, three readers pinned by a test.
- **one refused sub-read discarded every other field.** It now degrades to
  `None` — never `0`, which would fire QUEUED as though the provider had
  emptied the queue.

491 now reads clean: `queue_rows 647, emails_sent 281, sent_rows 281`.

---

## 8. THE TEST IDENTITY

the test identity's profile and leads **204966 and 204967** are excluded from every count by
`src/testidentity.py` — suppressed at the notification **write** and excluded
at the count **read**, because suppressing the write does nothing about rows
already in the feed. Both leads read `stopped`; the record is
`do_not_contact`. Registering it in 491's `record_ids` is safe *because* the
exclusion is by identity rather than by absence.

---

## 9. STILL NOT STARTED

Both new directives (research pack, copy quality). The **empty-body push
guard** — the single highest-value item outstanding, and §1 is its
justification. Roles from Slack membership. Watchers for 496/497/498. Why
four truedigital contacts landed together. rules-4, ledger write-back,
forward book from per-mailbox counters, AU ninth campaign, 289 re-engagement,
export sample, gag items, supervisor adoption, the reboot drill with
`cold_start --verify`, the S5/S7 supply pipeline on the 23,363 MX-open
domains.

---

## 10. THE PATTERN, AGAIN

Three more tonight, all the same shape — **the failure looked exactly like
the success**:

    a stop that never ran       the loop printed "stopped on both channels"
    a stop that COULD never run the verb read a contact field that has
                                never existed, and was sealed so nobody saw
    a blank email               every local check passed; only the
                                PROVIDER's record of what it sent was wrong

And one new one worth carrying: **an alert can silence itself.** The
external-stop alert's first version matched the word "stop" in a sentence
about a bounce threshold, and would have attributed 495 to us. Its own test
caught it. A guard whose attribution logic is loose is a guard that reports
clean.

---

## 11. THE AGENT BRANCH IS MERGED, AND INTERNAL MODE IS VERIFIED LIVE

Four merge requests, merged together on operator instruction: **internal
assistant mode**, Increment 2, Increment 4, and **Phase D5** — the last of
which had been the oldest unmerged for days and whose `sender_summary` count
fix is now live. 7,048 insertions.

**The branch check mattered and nearly went the wrong way.** A two-dot diff
(`git diff master origin/slack-agent`) appeared to show the branch touching
`scripts/bison_watch_loop.py` and reverting the write-seal work done earlier
tonight. It was not: that was MASTER's side of the diff. The **three-dot**
diff (`master...origin/slack-agent`) is the one that answers "what did the
branch change", and it shows no `src/providers/`, no `config/.env`, no
`*_watch_loop.py` and nothing under `work/` — the three-session boundary is
respected. Merging on the two-dot reading would have been the TASK-229
mistake inverted.

Verified AFTER the merge rather than assumed: the test-identity hook still in
`slackagenttools` (the one file both sessions touched), `SUPPORTED` still 15
with `heyreach.stop_lead` enabled, the `linkedin`-field fix still in
`leadstop`.

**Internal assistant mode's own measurement is the part worth carrying:**
drafting was never being refused. `"write a short summary of how the stop
works"` failed because `stop` is an action verb appearing there as a **noun**.
So the increment is a prompt change for internal scope plus a verb-matching
fix — not a licence to act. `COMPOSE_OPENERS` requires the verb to be the
opener, so `"pause 491 and write it up"` is still refused, and scope selection
is by exclusion so a fourth scope added later starts locked down.

**Loop restarted (pid 37556), reconnected, and verified live.** Asked in
`#resonate-os`: *"explain in three sentences how the cross-channel stop
works"*.

    ANSWERED C0C3C6MDN9L:1790189207.896399 scope=internal via=model
      tools=['cadence_detail', 'decisions_log', 'workspace_summary']

`via=model`, not a refusal and not a clarify loop. **And it did better than
comply:** it said the knowledge pack carries no named "cross-channel stop",
separated what it could evidence from what it was inferring — *"I'm
reasoning, not reporting"* — named what would settle it, and offered a ticket.
It is also correct: the stop lives in `inbound`/`leadstop`, not in the cadence
library, so it genuinely is not in the pack. **That is a real gap in the
agent's knowledge pack and it is a finding, not a fault.**

---

## 12. THE HYGIENE GUARD: ONE NARROW EXEMPTION, AND IT IS GREEN

**OPERATOR DECISION.** `src/testidentity.py` must name what it excludes, and
the hygiene guard forbids real identifiers in tracked files. A safety
mechanism and a privacy guard that could not both be satisfied.

**Resolved by a narrow, documented exemption for exactly two files**, listed
in `HYGIENE_EXEMPT` in the guard itself with the reason:

    src/testidentity.py
    tests/test_the_test_identity_is_never_counted.py

**Two fixes were rejected and why is recorded beside it.** A sidecar in
`work/` was refused: the module would then depend on a file that can be
missing, and there is no safe answer when it is — suppress everything and
real client notifications are lost, suppress nothing and the client is told
about the operator. A safety mechanism must not have a failure mode that
depends on a gitignored file being present. Allowlisting the real handle in
`FAKE_VANITY` was refused because it retires the guard for exactly the person
it protects, everywhere, for ever.

**Every other occurrence was scrubbed** — `notify.py`, `slackagenttools.py`,
`config/clients/productive.yaml`, `scripts/stage_s3_icp.py`,
`HUMAN-ACTIONS-REQUIRED.md`, all three handoffs, and the fixture addresses
that arrived with the agent merge (`src/replies.py`,
`test_the_class_layer_before_composition.py`). They reference
`testidentity`'s constants or say "the test identity".

**Three new tests keep the exemption the size it was argued for:** it must be
exactly those two paths, no entry may be a directory or a pattern, every
entry must actually be tracked, and — the load-bearing one —
`test_the_identifiers_appear_nowhere_ELSE_in_the_repository` fails if the
identifiers spread again, because two exempt files stop being sufficient the
moment they do.

**17/17 green.** The agent branch was given the same decision.

---

## 13. A CORRECTION: LEAD 204967

`tests/test_the_test_identity_is_never_counted.py` used lead **204967** as its
example of a lead that is NOT the test identity. 204967 then BECAME the second
test lead when the stop test was re-armed, and the assertion had been claiming
the opposite of the truth from that commit until the merge surfaced it.

Both **204966 and 204967** are test leads and both are named in
`testidentity.LEAD_IDS`. The non-matching example is now 204968. The lesson is
small and exact: **a fixture that encodes "this value is not special" has to be
re-checked whenever the special set grows**, and the suite should have been
re-run at the moment `LEAD_IDS` changed rather than at the next merge.

---

## 14. THE NEXT THREE ITEMS, IN ORDER

1. **Watchers for 496, 497 and 498.** `MONITORS` holds none. All three are
   ACTIVE. 497 is where the blank emails were found — by hand, because nothing
   was watching it. This is first precisely because the incident in §1 was
   invisible for that reason.
2. **Roles from Slack membership**, as decided: non-external members of the
   internal channels are Resonate users (DMs included), external members of a
   bound client channel are that client's users, everyone else unbound;
   refresh on start and hourly; post the resolved internal names once in
   `#resonate-os`. The three placeholder ids (`<ID_1>`…`<ID_3>`) are
   superseded by this and must not be used.
3. **The incident gate** — the empty-body push guard: refuse any push where a
   required `BODY_n` is empty or `"None"`, `str(None)` never reaches a
   provider variable, with tests. §1 is its justification and it is the single
   highest-value item outstanding.
