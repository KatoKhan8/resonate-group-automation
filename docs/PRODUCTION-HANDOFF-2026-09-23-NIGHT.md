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
13:15, 14:28, 14:30 UTC). **`paul.bradley@truedigital.co.uk` REPLIED to
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

**Why four truedigital.co.uk contacts landed in one campaign on one day is
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
   Target was the operator's own test profile (`/in/zbeslic`, `Finished`,
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

`/in/zbeslic` and leads **204966 and 204967** are excluded from every count by
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
