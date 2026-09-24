# Production handoff — 2026-09-24 evening

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-24-MIDDAY.md` and its two addenda.**

Lane 1, production: supply and quality only, under the FOCUS directive valid
to 2026-10-01.

---

## 1. THE ESTATE, RIGHT NOW

    campaigns   10 active, 0 paused, 1 archived (495)
    monitors    21 derived, all UP on two witnesses
    blanks      0 pending anywhere
    sent today  0 in our campaigns (provider-confirmed, two sources)

**491 and 481 are both resumed**, on operator authority recorded on the
provider write itself. 491: 274 `sending_paused` became 274 `scheduled`, 273
in sequence. 481: 9 in sequence, 14 stopped.

**Nothing has been pushed to a campaign today.** The batch is blocked — §4.

---

## 2. WHAT LANDED ON MASTER TODAY

Two branch merges and eleven fixes. In rough order of how much they matter:

- **`c1d93e94` witness 1.** `cold_start --verify` could never pass: only
  `supervise.py` wrote the state file it reads, and this estate is started by
  `start_monitors.py`, so `work/supervisor/` did not exist. Four handoffs
  read that as a broken drill. `supervisor.record_started` is public now and
  `spawn` calls it. **20 of 20, then 21 of 21, on two witnesses.**
- **`5257adbe` the denylist.** `emptyrender.scan` filed anything not in
  `{scheduled, queued, pending, ""}` as `already` — so a paused campaign's
  rows read as contained. Now `SETTLED_STATUSES = {sent, stopped, bounced}`
  and everything else is pending. A new status, `queued_for_sending`,
  appeared in the estate the same afternoon and the denylist handled it.
- **`d6a719c2`** every external-stop CRITICAL named campaign 487, because the
  call site passed a module constant instead of `watched`.
- **`1481a747` rules-4** with `RULE_HASH` derived from every pattern group,
  so a stored verdict names the rules that made it. This closes the gag's
  third fault.
- **`d7f3128a` / `a3c02e08`** the client export had no verdict gate at the
  reader and would have shipped 1,394 REVIEW rows; then the whole 1,508-row
  pool was retired, gated on provenance so it self-clears.
- **`e644c040`** the Monday report loop beat into a filename built from its
  own state dict.
- **`33c1b364`** `testidentity` carried the wrong domain — see §5.
- **`236eeef7` / `d892ca14`** the infra and slack-agent merges.

---

## 3. THE RULE I GOT WRONG THREE TIMES TODAY, WRITTEN DOWN

**I asserted absence from a lookup on a name I had not verified, three
times, and twice it reached a CRITICAL post.**

1. **481's "five empty steps".** I read `s.get("subject")` and `s.get("body")`
   on a sequence step. The keys are `email_subject` and `email_body`. Both
   returned `None`, and I reported "ALL FIVE EMPTY, subject '', body length
   0" as a measurement. The steps are ordinary merge templates. I refused a
   campaign the operator had told me to resume, on that.
2. **"`heyreach.stop_lead` does not exist".** `hasattr` on a name I invented.
   It is `heyreach.stop_lead_in_campaign`, wired through
   `providerwrites.LINKEDIN_STOP_LEAD` into `leadstop.py:190`. I recommended
   infra build something that already existed.
3. **"The 9 `sending_paused` leads are the 9 foreign ones".** Two counts of 9
   among the same 23 records, joined in prose, never cross-tabulated. They
   are disjoint sets.

**The check that costs ten seconds and would have caught all three:** print
the object's keys, or `dir()` the module, before concluding something is
missing. `None` from a `.get()` is not evidence of emptiness, and `False`
from a `hasattr` is not evidence of absence.

**What caught #3 is worth keeping:** the containment script selected its
targets by reading each lead's variables rather than trusting the membership
label, so it found 0 to stop and did nothing. Written the obvious way —
"stop the 9 `sending_paused`" — it would have stopped nine healthy leads.
**Select on the property you care about, never on the label you inferred it
from.**

---

## 4. THE BATCH, AND THE FORWARD-BOOK RULE

**Tonight's cohort is 179 leads across 153 accounts**, from 229 clean ones.
Not the 330 the plan printed: `batch1_build`'s pacing rule selects without
asking whether the account is already in the store, and the clash check only
runs at `--write`. 212 of its 304 accounts are already enrolled — 506 of
batch-3's 515 records carry a `bison_lead_id`. **The guard was right.**
`--fill-existing` is the supported path that excludes them.

**Then every campaign returned `room 0`, and the cause was a stale
instrument, not a full estate.** `work/forward-book-census.json` was 30.4h
old against `STALE_AFTER_HOURS = 24`, so `senderheadroom` returned REFUSED —
and **REFUSED IS NOT ROOM**. Re-running it is not quick: 14 campaigns, three
of them the client's own, and 352 alone reports ~95,000 rows. They must be
walked because they book the same mailboxes we send from.

### 4.1 THE 50% CEILING — operator rule, 2026-09-24

Until the census is fresh, room per mailbox is:

    room = (daily_limit - sent_today - our scheduled rows for today) x 0.5

**The halving is the whole point.** The client's own campaigns book the same
mailboxes and their bookings are unknown while the census is stale, so half
the apparent room is reserved against them. This rule is a stand-in and is
**replaced by the census the moment it completes** — it is not a new default.

---

## 5. THE TEST IDENTITY WAS ON THE WRONG DOMAIN

`testidentity.EMAILS` recorded the operator's address on **the wrong
domain** — a near-miss of the real one, close enough that nobody reading it
would notice. The addresses themselves are in `src/testidentity.py`, which is
the guard's one exempt file; they are deliberately not repeated here.

`notify.py` calls `testidentity.matches` to SUPPRESS everything about that
identity, so a test reply is never counted as a prospect reply nor surfaced
to a client. Matching the operator's **real** address returned **False**.

Tonight's email→LinkedIn measurement would therefore have had the operator's
own reply counted as a real prospect reply and eligible to reach a client
channel — the exact outcome the module exists to prevent, defeated by a
misspelling of the identity it protects.

**Both domains are now held.** Leads 204966 and 204967 genuinely carry the
original at the provider, confirmed 2026-09-24, so dropping those entries
would un-suppress the two leads the module was written for.

**It was found by the operator correcting me in passing, not by any check.**
Nothing asserts that the recorded identity resolves to a real mailbox.

---

## 6. THE 09-07 FUNNEL, AND WHERE THE BACKLOG IS

    S3 ICP 24,404  ->  in 19,612 · flagged 4,629 · out 163
    MX     24,241  ->  allowed 20,357 · unknown 3,022 · blocked 660
    S5     11,017 attempted  ->  verified 6,671 · held 3,383
    S7        927 reached    ->  rendered 814 · held 113
    READY     927            ->  ENROLLED 675

**8,595 domains cleared ICP and MX and have never had an address verified.**
Not blocked — never walked. S5 measured **0.40 addresses/s, 351 minutes for
8,387**, and that single number is what stands between the estate and the
19,612. Parallelising it to each provider's documented limit is the highest
-value open item.

---

## 7. OPEN, IN THE OPERATOR'S ORDER

1. **Push the 179 on the 50% ceiling** (§4.1), samples, veto, post-attach
   readback, activate. Census keeps running.
2. **Re-engagement tonight.** The REENGAGE lane from the 2026-09-22
   inventory — contacted 90+ days ago, no reply ever, no unsubscribe, no
   bounce — US subset (289) first. **The REVIVE lane stays out: human drafts
   only.** Never a store record carrying a reply or an unsubscribe. The
   inventory is `work/stage/reengagement-inventory.jsonl`, 2,081 rows.
3. **S5 parallelism** on the 8,595.
4. **The account rule rewrite.** Corrected by the operator: one new person
   per account per week means STAGGERED, not blocked. Same contact = refuse.
   Same account, different persona = allow once the first has 5 days with no
   human reply; a third after 7 more. Any reply or unsubscribe from anyone at
   the account stops all others. The 212 accounts refused tonight are the
   direct beneficiaries.
5. **Steps 4 and 5 copy**, for the operator's "approve steps 4-5". Note the
   ordering problem: `em3` is currently `breakup`, which says "I will leave
   it here" — two further steps after it would make that false. The 5-step
   cadence has to move breakup to the end.
6. **The email→LinkedIn measurement.** `heyreach.stop_lead_in_campaign`
   exists and is wired; its own docstring says **NEVER LIVE-VALIDATED**. That
   is what the measurement is for, not the function.

---

## 8. FROZEN, CARRIED TO OCTOBER

ISSUE-025 remove-lead verb (also blocked on ISSUE-030: no documented route
detaches a lead from a campaign, and `DELETE /leads/{id}` is not it — those
are the client's own leads). Client-two runbook. Ledger write-back beyond the
status post. The learning doc beyond Friday's scorecard. The reboot drill.
Meta Muse Spark as the reply composer, with the operator's scoring design.

**Credential rotation is DEFERRED by the operator** — five values were found
live, the archive is redacted on disk, and it is not to be raised under NEEDS
ME again or allowed to block work.

---

## 9. THE PATTERN, AGAIN

**Every headline number today came from a stage that had not asked the next
stage's question.** 1,508 exportable that was 114. 19,612 "IN" of which
two-thirds are under the 20-person floor. 330 selected of which 212 were
spoken for. A 19:00 ETA sized on a builder whose input had expired six hours
earlier. In every case the later gate was right and the earlier count had
already been quoted.

**A guard that refuses is not a guard that is wrong.** Three refusals today —
the double-enrolment clash, the stale forward book, the write-scope refusal —
were all correct, and in two of them my first instinct was that the guard was
being over-cautious. Checking took minutes and the guard won every time.


---

# TOMORROW, IN THIS ORDER — operator, 2026-09-24 night

Not a wish list. This is the order, and 1 gates 2 gates 3.

## 1. RETIRE THE `last_touch` CACHE

The last confirmed touch for **any** decision — collision recency,
re-engagement age, account gaps — is read from **the provider's sent rows at
decision time**, never from a cache older than the current cycle.

**Test required: a lead sent to yesterday can never read as untouched for 90
days.**

Why, measured tonight: `work/stage/last-touch.json` is a cached copy that is
never refreshed. 145 of 2,081 rows are staler than the live lead, 133 by 7+
days, the worst by 111. **Lead 133283's inventory age read 111 days; its last
confirmed send was 2026-09-22T19:40:34Z, from our own campaign 491.** Thirteen
leads emailed one or two days ago sat in a cohort qualified as
"contacted 90+ days ago".

This is first because every rule below depends on knowing when somebody was
last written to.

## 2. THE ACCOUNT RULE AND THE COLLISION GATE, TOGETHER

One change, one review — they teach the same system the same distinction.

    same contact                                  NEVER twice
    same account, new persona                     allowed after 5 days
                                                  with no human reply
    third persona                                 7 days after that
    any reply or unsubscribe at the account       stops all others
    a stop carrying OUR OWN reason plus an
      operator-recorded move                      is NOT an account-level hold

**Tests first. GLM review before merge.** The last clause is ISSUE-035: the
gate is right to hold an account where a campaign ended early, and it cannot
currently tell a deliberate move of ours from an observed fault.

## 3. THEN, AND ONLY THEN

- The 63 into fresh campaigns — **500 already exists, empty and paused, for
  Luka**; Bojan and Jakov need theirs. They are blocked on 2, not on capacity.
- The US batch: 5 steps if the operator has approved steps 4-5, packs where
  they exist.

## AND A STANDING WORKING RULE

**Every code-editing background agent gets its own git worktree. The main
checkout belongs to the foreground session alone.** Set after agents left the
main checkout on a feature branch, which sent a production commit to that
branch and pushed an unrelated agent's work to master instead.
