# The cross-channel stop measurement is staged and waiting on one email

Everything is built. The only thing missing is a send the provider has
scheduled for **2026-09-25T15:48:00Z**. Nothing here needs rebuilding, and
nothing here should be rebuilt — rediscovering it costs an evening, which is
what it cost.

---

## 1. WHAT IS STAGED, BY ID

    EMAIL   campaign 501  "RESONATE - STOP TEST - 2026-09-24 LATE"
            active · 1 step · wait_in_days 1 · 7-day 00:00-23:59 Europe/Zagreb
            sender 4286 k.simicic@gproductive.com · Connected
            lead 205081  zvonimir+stoptest@resonategroup.co  in_sequence
            scheduled send 2026-09-25T15:48:00Z  (step 4778)

    EMAIL   lead 205079  zvonimir@resonategroup.co  in_sequence on 491
            the ORIGINAL test lead. 491's window is 09:00-17:00
            America/New_York, so it sends on its own schedule; 665 rows are
            queued there with the next batch around 2026-09-25T14:30Z.
            Either lead replying exercises the same chain.

    LINKEDIN campaign 620829 "RESONATE STOP TEST"  IN_PROGRESS
            seat 174892 · 00:00-23:30 GMT · one lead, the operator
            leadStatus InSequence  <- A RUNNING STATUS. This is the point.

    RECORD  crosschannel-stop-test-2026-09-23, client productive
            contact zvonimir-beslic
              bison_lead_id      205079
              heyreach_lead_id   ACoAACj2VAEBNFrv0vIdobwRkkkK6QUEQwNoDfI
              linkedin           https://www.linkedin.com/in/zbeslic

    CAMPAIGN ROW  productive-linkedin-stoptest-620829
            heyreach_campaign_id 620829 · status draft · daily_volume 0
            not_launched · holds exactly one record. Nothing sends from it.

---

## 2. WHY IT IS A REAL TEST AND NOT A PASS BY CONSTRUCTION

`heyreach.stop_lead_in_campaign` reads back per lead and **raises** when the
provider still reports the lead in a running status:

    RUNNING_LEAD_STATUSES = ("Pending", "InSequence",
                             "PendingOrExcludedToBeCalculated")

620829 reports **InSequence**. So the stop must genuinely move the operator
out of a running status or the readback refuses. That is the whole reason a
new campaign was needed: on 613744 the same identity reads **Finished**, and a
stop against a settled lead returns "already settled" — a pass by
construction, which is the shape of the first blank-content halt that alerted
and halted nothing and read as working.

**Do not run this against 613744.** It is still listed for the identity and it
is still Finished.

---

## 3. THE THREE THINGS THAT WERE BROKEN, ALL FIXED ON MASTER

Without these the measurement would have reported success while measuring
nothing. Registered as ISSUE-041, 042, 044; fixed in `5cd5173d`.

1. **No contact in the store carried `heyreach_lead_id` — not one.**
   `inbound._stop_at_provider` gates the LinkedIn stop on that field and
   renders its absence as `"linkedin: no lead"`, which the code explicitly and
   correctly does **not** treat as a refusal. The reply would have reported
   `"email: stopped; linkedin: no lead"` and `stop_lead_in_campaign` would
   never have been called. That is why its docstring still says NEVER
   LIVE-VALIDATED.
2. **`leadstop._campaign_of` resolved channel-blind**, so the LinkedIn stop
   would have been handed the EMAIL campaign row and raised StopRefused.
3. **`testidentity.matches(205079)` was False** on the lead id alone, and an
   EmailBison event can carry the lead id and nothing else. The operator's own
   reply was eligible to be counted as a prospect reply and reach Productive's
   channel — the 09-23 incident reproduced by the process fixing it.

`reply_watch` and `notify_deliver` were restarted at 23:44 so the running
processes hold the fixed modules. **If either is restarted from a checkout
that is not master, check `testidentity.LEAD_IDS` carries 205079 and 205081
before letting a reply land.**

---

## 4. HOW TO RUN IT

1. Confirm the email actually sent — `bison.scheduled_emails(501)` shows
   `sent_at` non-null, or `lead(205081).lead_campaign_data[0].emails_sent > 0`.
   **Do not tell the operator to reply before this.** They were told to reply
   once already when nothing had been sent, because every campaign in the
   estate is outside its send window at night (ISSUE-045).
2. Post in `#resonate-os` asking them to reply, and **record the timestamp of
   their reply** — the 15-minute gate is measured **reply -> stop**, not from
   the post.
3. Watch `heyreach.campaigns_for_lead("https://www.linkedin.com/in/zbeslic")`
   for campaign 620829's `leadStatus` leaving the running set.

**PASS** = leadStatus leaves `Pending`/`InSequence`/`PendingOrExclu...` within
900 seconds of the reply, with `stop_lead_in_campaign` returning its readback
rather than raising.

**NOT a pass**, and each of these has a specific prior cause:
- `"linkedin: no lead"` — the binding is missing again (§3.1).
- `StopRefused ... names no HeyReach campaign` — the campaign row is gone or
  `_campaign_of` regressed (§3.2).
- Any result against a lead already `Finished` — §2.
- A stop reported without a provider readback quoted.

Evidence lands in `work/notifications.jsonl`, the action ledger, and the
record's own `events`. A scratch watcher was used on the night and is **not**
required: the production loops record the whole chain.

---

## 5. WHAT THIS GATES

The operator's standing condition: **the halt lifts and the 825 enroll across
33 seats under the 07:00-23:00 seat-local schedule only if the stop completes
inside 15 minutes in BOTH directions.** LinkedIn -> email passed at 7.7 minutes
on 09-23. Email -> LinkedIn is this measurement and has never run against a
live lead.

Until it does, the halt stays on. A measurement that cannot fail is not
evidence for enrolling 825 people.
