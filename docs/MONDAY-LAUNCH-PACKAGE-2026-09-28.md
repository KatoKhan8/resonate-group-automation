# MONDAY LAUNCH PACKAGE — three cohorts of 100, prepared 2026-09-26

**Operator priority 2, 2026-09-26:** three cohort campaigns of 100 leads each on
the v2 engine, existing cadence and gates, a review file for each, so replies can
be measured for one week. **Prepare it; do not activate.**

**Nothing here is activated, sent, attached or enrolled.** The production freeze
in `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` stays in force. Activation
needs the operator's explicit **APPROVED** and the freeze exception.

---

## 1. THE BLOCKER: there are not 300 leads, and freshness cannot be established

Measured against `work/queue.jsonl` (1,582 records, all client `productive`) on
2026-09-26:

    qualified accounts (icp_status = qualified)          113
      minus drop_reason "no contact found"              104
      with at least one usable contact                   85
    USABLE CONTACTS (email present, not unsubscribed)   237

    needed for 3 x 100                                  300
    SHORTFALL                                            63

The rest of the estate: 215 accounts are `review`, 222 are `rejected`, and 1,032
records carry no qualification at all.

### The more serious problem: 237 is a paper number

**The queue records no send events.** Across all 1,582 records the only
outreach-shaped events are `reply_received` (28), `reply_classified` (28),
`positive_reply_detected` (2) and `push_marked` (1). There is no `sent`,
`delivered`, `attached` or `enrolled` event anywhere.

So **local state cannot tell us which of those 237 contacts have already been
emailed** by campaigns 491-505, which the handoff records as having sent 411 + 245
+ 95 + 25 + 14 + 25 and more. Some unknown portion of the 237 has already been
contacted.

This is exactly the shape of the 2026-09-23 incident: **44 of the 46 blank leads
in 491 were already in a client campaign**, and nobody knew until after the send.
Selecting 300 leads from this inventory without establishing contact history
risks re-contacting people, and the same 18-of-22 collision the operator already
accepted on 493 exists here unmeasured.

**TASK-349 closes precisely this gap** — ledger write-back of provider sends and
replies. It is dispatched and running. **The cohort selection should not be
finalised before it lands**, or the selection is a guess.

---

## 2. WHERE THE LEADS COME FROM

Two sources, and the first one alone is not enough.

**a. The existing 237.** Available immediately, freshness unestablished (above).
Enough for two cohorts, not three.

**b. `TASK-347` — the client file, 35,043 rows.** Dispatched and running:
batches of 1,000 through qualification → MX → CheapVerifier → packs → facts,
stopping before copy. **This is the only path to a third cohort of genuinely
fresh leads**, and the operator's own standing note applies: *"Expansion is a
sourcing problem, and latency is a sender problem — they are different problems
with different fixes."*

At the measured qualification rate on the current estate (113 qualified of 550
scored ≈ 21%), one batch of 1,000 should yield roughly 200 qualified accounts —
comfortably enough for the shortfall, but **that rate is an estimate from a
different sample and must be replaced by TASK-347's measured number.**

---

## 3. WHAT THE THREE COHORTS SHOULD BE

`PRODUCTION-SCALE-POLICY.md`: a campaign is a **COHORT and never a person**,
~50 qualified leads per normal cohort, signal-based grouping backed by evidence
that actually exists, consolidation over proliferation.

100 per cohort is double the normal size, which the operator has asked for
deliberately so a week of replies is measurable. Grouping must still be by a
real signal, not by an arbitrary split of 300:

    Cohort A   the strongest qualified segment by ICP tier and confidence
    Cohort B   the next segment, a DIFFERENT persona or capability
    Cohort C   fresh leads from TASK-347, a distinct segment again

**Three cohorts on the same segment would measure the same thing three times.**
The point of three is a comparison, so each needs a different persona, capability
or angle — and that decision belongs to `TASK-320`'s per-segment strategy, which
is blocked behind the Offer Engine recovery (`TASK-333`).

---

## 4. COST, MEASURED RATHER THAN ESTIMATED

From the fifty, whose real cost was $3.1464:

    per written lead                               10.15c
    300 written leads                              $30.45
    of those, expected to pass BOTH gates             126   (42%, measured)

    to obtain 300 GATE-PASSING leads
      written leads required                          715
      cost                                         $72.61

**This is the number that matters and it is the one the handoff obscured.** "100
leads per cohort" means something different depending on whether it counts leads
processed, leads written, or leads that pass copylint and sequencegate. On the
fifty, 50 in produced 31 written and **13 sendable**.

    3 x 100 written   -> ~126 sendable   -> $30.45
    3 x 100 sendable  -> 715 written     -> $72.61

Sonnet is 95.8% of that either way. `TASK-340` has now built prompt caching and
batching but **the measurement of what they save is still owed** — and cannot be
trusted yet, because `model-prices.yaml` does not price
`cache_creation_input_tokens` or `cache_read_input_tokens` separately, so a cached
run would be mispriced.

**Which of the two readings the operator wants changes the cost by 2.4x and the
generation volume by 2.4x.** It needs answering before generation starts.

---

## 5. WHAT IS UNCHANGED, AND MUST STAY SO

- **Five email steps** at days 1/4/8/12/21, threading em1 new/A, em2 reply A, em3
  new/B, em4 reply B, em5 new/C.
- **Five LinkedIn steps** in `PRODUCTIVE_LI_HEAVY_V1` at days 1/3/6/10/15, across
  the two branches documented in `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`.
- **Every gate**: `reviewapproval.require`, `providerwrites.perform`,
  `spendledger.check`, `copylint.check_batch`, `sequencegate.check`,
  `emptyrender.scan`, and the `attach_leads` refusal into a live campaign.
- Suppression and DNC, including the 76 recipients suppressed after the 09-23
  incident.

---

## 6. WHAT MUST BE TRUE BEFORE THIS CAN BE ACTIVATED

A checklist, not a formality. Each line is a thing that has gone wrong here
before.

1. **`TASK-349` landed**, so contact history is known and the 237 can be filtered
   for who has already been emailed. Without it the selection is a guess.
2. **Collision checked against the client's own campaigns** 327 and 328. 493
   carries an accepted 18-of-22 collision; a new 300 must be measured, not
   assumed.
3. **A review file per cohort**, verified against the ten's shape the way the
   fifty was: threading, both P.S. lines, signature, four LinkedIn messages,
   facts with first-party sources, and **the per-gate result per lead**.
4. **The gate results read before approval, not after.** The fifty looked like 31
   usable leads and was 13.
5. **`TASK-343` landed**, so the review files' LinkedIn days are read from the
   cadence rather than hardcoded. Today the preview shows days 1/3/8/14 where the
   graph says 1/3/6/10/15.
6. **The signature question answered** (`TASK-341`). Every step currently renders
   "none stored on this mailbox", so 300 leads x 5 steps would go out unsigned.
7. **`booking_link` fixed or the CTA changed.** It is
   `https://productive.test/...`, a reserved TLD that resolves nowhere. Any CTA
   offering a link currently offers a dead one — for 300 people.
8. **Sender capacity confirmed against the forward book**, not the mailbox count.
   2,310/day is a cap; 1,470 was what was actually free. 300 leads x 5 steps is
   1,500 sends over 21 days and must fit the senders that are genuinely free.
9. **Spend authorised** for the generation volume chosen in §4.
10. **The operator's explicit APPROVED**, with the approval hash of each cohort's
    review file — and note that `reviewapproval.require` does **not** currently
    check that hash (`TASK-328`), so until it lands the hash is an audit record
    rather than an enforced pin.

---

## 7. RECOMMENDED ORDER

1. `TASK-347` finishes batch 1 and reports its real qualification rate and spend.
2. `TASK-349` lands; filter the 237 for genuine freshness.
3. Operator answers §4: **100 written per cohort, or 100 sendable per cohort?**
4. Cohort definition from `TASK-320`'s per-segment strategy once `TASK-333` lands.
5. Generate, under an explicit cap, with gate results per lead.
6. Three review files, verified against the ten's shape, posted with hashes.
7. Operator reviews, grants the freeze exception with **APPROVED**.
8. Activate — and only then.

**Items 1, 2, 4 and 5 are in flight now. Item 3 is a question only the operator
can answer, and it is the one that gates the generation volume.**
