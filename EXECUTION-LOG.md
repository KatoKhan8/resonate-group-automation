# Execution log — real Productive data

What has actually been run against the real Productive estate, what it
measured, and what that says to do next. Durable on purpose: a restart must be
able to answer "what was planned, reserved, attempted, confirmed, recorded"
without re-deriving it from a transcript.

Every number here is **MEASURED** unless labelled DERIVED or UNKNOWN. Nothing
is estimated into a gap.

---

## 2026-09-12 — first real processing run

**HEAD** `d0b2bf9` · suite 7,548 green at `21cb8f9`, focused green since ·
tree clean

### Funnel, measured (`python -m src.funnel`, 300 records)

| stage | count | of | rate |
|---|---|---|---|
| input_domains | 300 | | |
| valid_domains | 300 | 300 | 100.0% |
| company_facts | 265 | 300 | 88.3% |
| researched | 79 | 300 | 26.3% |
| scoreable | 264 | 265 | 99.6% |
| **confidence_medium_or_high** | **10** | 264 | **3.8%** |
| qualified | 9 | 264 | 3.4% |
| people_found | 12 | 9 | x1.33 |
| emails_found | 12 | 12 | 100.0% |
| emails_2_of_2_verified | 5 | 12 | 41.7% |
| campaign_ready | 1 | 12 | 8.3% |
| approved | 1 | 1 | 100.0% |
| provider_staged | 0 | 1 | x0.0 |
| readback_verified | MISSING | 0 | |
| live | 0 | MISSING | |
| replied / positive / meeting | 0 / 0 / MISSING | | |

Attrition, dominant reason per record: ICP_REJECT 98 (the system working),
RESEARCH_NOT_RUN 82 (bounded, recoverable by spending), ICP_REVIEW 41 (human
queue), NO_PROVIDER_COVERAGE 35, LOW_CONFIDENCE 31, READY 4,
EMAIL_VERIFY_FAILED 4, MISSING_EVIDENCE 4, NO_PERSON 1.

### The bottleneck, and the measurement that located it

`confidence_medium_or_high` is 3.8%. The missing-evidence tally says why, and
it is the same five dimensions on nearly every record:

    300/300  no evidence for time tracking need
    299/300  no evidence for utilization need
    298/300  no evidence for profitability need
    298/300  no evidence for operational complexity
    293/300  no evidence for resource planning need

These are Productive's own product-fit dimensions. A company website does not
say "we struggle with utilization", so they are absent by construction rather
than by a gathering failure. Three confidence components are flat zero
regardless of effort: `source_diversity` 0.0 on 300/300, `recency` 0.0 on
300/300, `source_quality` 0.0 on 260/300.

**The obvious conclusion from that is wrong, and was tested rather than
assumed.** Research still moves the needle:

| | n | medium+high confidence | mean ICP score |
|---|---|---|---|
| researched | 72 | **13.9%** | 23.9 |
| not researched | 228 | **0.0%** | 7.8 |

Coverage rises from a 0.417 ceiling unresearched to 0.75 researched. Research
is the ONLY path to medium confidence in this model, so finishing it is
correct. DERIVED from that rate: the 192 unresearched records should yield
roughly 27 more medium/high and a small number of additional qualified
companies. That projection is a rate extrapolation, not a measurement.

### Throughput, measured

- Apify research: **~86s per company** wall clock (`scrape_started` →
  `scrape_completed` on `arian-com`, 13:02:43 → 13:04:09).
- The run is I/O bound, not CPU bound: 3s of CPU over ~40 minutes.
- DERIVED: 192 remaining × 86s ≈ **4.6 hours** to finish company research.
- Free stages (qualify + personas) over 275 records: **3.2s total**.

### Spend, measured

Ceiling set this session (runaway guard, not a cost target): per_day 5000,
per_run 2000, total 50000. Before it, all four scopes were null and the shard
preflight answered UNBOUNDED.

Today: 15 ledger rows, **3 credits** — 12 `apify-research` (0 credits; Apify
bills compute units the credit cap cannot read), 1 `email-verifier`, 1
`deliverable-verify`, 1 `reoon-verify`. Lifetime 197 credits before today.

The three verification rows are the first that have ever reached this ledger:
until today `verification.verify` wrote only the per-record waterfall, so the
durable spend audit under-reported by exactly the verification bill.

### Provider truth — HeyReach 594061

Reconciled three times today, unchanged each time:

    campaign  IN_PROGRESS, started 2026-09-09T18:07:51Z, org unit 118832
    progress  totalUsers 1, inProgress 1, finished 0, failed 0
    stats     connectionsSent 0, accepted 0, replies 0, uniqueLeadsContacted 0
    lead      304173736 Brooke Baron, state request_pending, sender 116968
    seat      116968 active, auth valid, no cooldowns, 9 active campaigns

Provider truth, action ledger (absent — nothing ever reserved), confirmed
touch (none) and canonical state all agree: **CONFIRMED_NOT_EXECUTED**. No
retry, no duplicate action.

**Open question, not a defect yet:** three days IN_PROGRESS with an active
seat and zero connections sent. The seat carries 9 active campaigns, so
starvation by the seat's own daily quota is the leading hypothesis. It is a
HYPOTHESIS; nothing has been changed on its account.

### Estate context that matters

The client's HeyReach estate is heavily worked: dozens of campaigns on org
unit 118832, many IN_PROGRESS. That is the reason the account-level collision
gate exists, and it means a meaningful share of the TAM has already been
touched by somebody else. Any promotion ladder must assume that.

### Remaining manual operations

- 41 records sit at ICP_REVIEW: a human verdict, or better evidence.
- Both providers: campaign create, sequence, sender assignment and activation
  are done by hand in the vendor UI. On HeyReach the routes exist and are not
  allowlisted; on EmailBison no write verb is established at all.
- HeyReach per-campaign daily limit and schedule cannot be read back, so
  setting them in the UI is unverifiable from here.

### Highest-priority defect

`executionguard.authorize` performs four unscoped `actionledger` loads per
action (`count_on` twice, `contacts_reached`, `require_clear`), none passing
`rows=`. MEASURED: 1.45ms at 100 ledger rows, 110ms at 10k, 2083ms at 100k.
Harmless now (the ledger is empty) and quadratic in the number of live
actions, so it arrives exactly as the promotion ladder scales.
