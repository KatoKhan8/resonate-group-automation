# Intake Throughput Measurement — 2026-09-15

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
**Source pool:** 51,741 people → 20,944 unique company domains
**In queue:** 550 (2.6% of pool)

---

## 1. Per-Stage Counts and Per-Record Costs

### Pipeline stages and what they cost

| Stage | Records reached | % of 550 | Provider credits | Model calls | Deterministic? |
|-------|----------------:|----------:|-----------------:|------------:|:--------------:|
| Ingest | 550 | 100.0% | 0 | 0 | Yes |
| Qualify (classify+score+segment+route+plan) | 300 | 54.5% | 0 | 0 | Yes |
| Enrich: people-count | 300 | 54.5% | 0 (free) | 0 | Provider (free) |
| Enrich: decision-makers | 132 calls across 165 records | — | 1,320 | 0 | Provider (paid) |
| Verify: email (ContactOut+Deliverable+Reoon) | 97 | 17.6% | 405 | 0 | Provider (paid) |
| Draft: LinkedIn notes | 68 | 12.4% | 0 | 2,433 | **Model** |
| Draft: emails | 54 | 9.8% | 0 | 2,974 | **Model** |
| Approve | 35 | 6.4% | 0 | 0 | Human |

### Per-record cost (amortised across all 550)

| Cost type | Total | Per record (all 550) | Per sendable record (67) |
|-----------|------:|---------------------:|-------------------------:|
| Provider credits | 1,725 | 3.14 | 25.7 |
| Model calls | 5,407 | 9.83 | 80.7 |

### Provider credit breakdown

| Call type | Count | Unit cost | Total |
|-----------|------:|----------:|------:|
| people-count (ContactOut) | 661 | 0 | 0 |
| decision-makers (ContactOut) | 132 | 10 | 1,320 |
| email-verifier (ContactOut) | 81 | 3 | 243 |
| deliverable-verify | 81 | 1 | 81 |
| reoon-verify | 81 | 1 | 81 |
| MX check | 235 | 0 | 0 |
| **Total** | | | **1,725** |

### Model call breakdown

| Step | Calls | Records touched | Avg per record (when touched) |
|------|------:|----------------:|------------------------------:|
| draft (email) | 2,974 | 54 | 55.1 |
| linkedin_note | 2,433 | 68 | 35.8 |
| **Total** | **5,407** | **70** | **77.2** |

Model calls include retries from lint rejections. Min 6, max 230 per record.

---

## 2. Terminal States and Reasons

### State distribution

| State | Count | % |
|-------|------:|--:|
| queued | 316 | 57.5% |
| dropped | 125 | 22.7% |
| drafted | 44 | 8.0% |
| held | 36 | 6.5% |
| verified | 26 | 4.7% |
| approved | 3 | 0.5% |

### Where records stop (funnel halting points)

| Halting point | Count | Gate or gap? |
|---------------|------:|:------------:|
| Not yet qualified (raw intake, batch 0) | 250 | **Neither** — queued for qualify |
| Dropped: ICP rejected | 116 | **Gate working** |
| Queued: needs human review (ICP review/unknown) | 66 | **Gate** — awaiting decision |
| Drafted: awaiting approval | 44 | **Gate** — awaiting Claude approval |
| Held: unresolved email verification | 36 | **Gap** — provider could not resolve |
| Verified: awaiting draft | 23 | **Neither** — pipeline continues |
| Dropped: no contact found | 9 | **Gate working** |
| Approved: ready to send | 3 | Terminal (success) |

### Drop reasons

| Reason | Count |
|--------|------:|
| rejected at ICP: no person-level enrichment | 116 |
| no contact found at this domain | 9 |
| **Total dropped** | **125** |

### Held records: why

| Reason | Count |
|--------|------:|
| Enriched but email verdicts unresolved | 9 |
| persona_angle failed (evidence gaps) | 8 |
| Enriched, 3 provider calls, still unresolved | 4 |
| All personas excluded (0 kept) | 6 |
| Other (partial enrichment, lint failures) | 9 |

**Held is a gap, not a gate.** These records have contacts but verification could not reach a definitive answer (accept_all domains, provider timeouts). They are not rejected — they are waiting for a resolution path that does not exist yet.

---

## 3. ICP Rejection Detail

121 records received a rejected verdict; 116 of those were dropped.

### Rejection reasons

| Reason | Count | % of 121 rejected |
|--------|------:|-------------------:|
| Under client minimum of 20 employees | 101 | 83.5% |
| Geo outside client's stated markets | 17 | 14.0% |
| Geo excluded by client (India) | 1 | 0.8% |
| Other ICP flags | 2 | 1.7% |

### Employee size distribution of rejected companies

- Min: 1, Max: 501, Median: 5
- Under 5 employees: 50
- Under 10: 81
- Under 15: 101
- Under 20: 101 (all that were rejected for size)

The size gate is the dominant filter. The purchased list skews heavily toward micro-agencies (median 5 employees) well below the client's 20-employee minimum.

---

## 4. Cost of a 250-Account Batch (Derived from 550)

### Projected yield

| Stage | Expected from 250 | Calculation |
|-------|------------------:|-------------|
| Qualify | 136 | 250 × 54.5% |
| Pass ICP | ~74 | 136 × 54.5% (qualified+review pass) |
| Enrich (DM search) | ~74 | all that pass ICP |
| Verify | ~44 | 250 × 17.6% |
| Draft | ~24 | 250 × 9.8% |
| Approve | ~1–2 | 250 × 0.5% |
| Sendable contacts | ~30 | 250 × 12.2% |

### Projected cost

| Cost type | 250 batch | 500 batch |
|-----------|----------:|----------:|
| Provider credits | 784 | 1,568 |
| Model calls | 2,458 | 4,915 |
| Expected sendable | 30 | 61 |
| Expected approved | 1–2 | 3 |

### Cost per outcome

| Metric | Value |
|--------|-------|
| Provider credits per sendable contact | 25.7 |
| Model calls per sendable contact | 80.7 |
| Records processed per sendable contact | 8.2 |
| Records processed per approved | 183 |

---

## 5. Deterministic vs Model Stages

Cross-reference with TASK-149 (still in TODO, not yet landed):

| Stage | Type | What it does |
|-------|:----:|--------------|
| ingest | Deterministic | CSV parse, domain normalise, dedupe, suppress |
| qualify/segments.classify | Deterministic | Rule-based vertical/region/size from company_facts |
| qualify/icp.score | Deterministic | 12-dimension rule-based ICP scoring |
| qualify/routing.plan | Deterministic | Persona routing from segment + verdict |
| qualify/strategy.for_company | Deterministic | Messaging angles from segment + verdict |
| qualify/dmplan.for_company | Deterministic | Cost plan from verdict + persona plan |
| enrich/people-count | Provider (free) | ContactOut profile count |
| enrich/decision-makers | Provider (paid) | ContactOut DM search, 10 credits/call |
| verify/email | Provider (paid) | ContactOut + Reoon + Deliverable, 5 credits/contact |
| verify/mx | Provider (free) | DNS MX lookup + rule classification |
| **draft/linkedin_note** | **Model** | **LLM generates connection note** |
| **draft/email** | **Model** | **LLM generates email body + subject** |
| lint | Deterministic | Rule-based checks on generated drafts |
| approve | Human | Claude reviews and approves |

**The model is called only at the draft stage.** Everything before it is deterministic or provider-paid. The 5,407 model calls all come from 70 records (12.7% of the queue) that reached drafting.

---

## 6. Recommended Next Batch Size

### The arithmetic

The 250 records already in queue have **not been qualified yet** — they are raw intake from `productive-intake-00000-00250.csv` with zero company_facts, zero research, zero contacts. Qualify is free (no provider calls, no model calls). Running qualify on them costs nothing and will reveal how many pass the ICP gate before any credits are spent.

**Step 1: Qualify the 250 already queued.** Expected outcome based on current rates:
- ~136 will qualify (54.5%)
- Of those, ~74 will be qualified or review (pass ICP)
- ~62 will be rejected (under 20 employees or wrong geo)

**Step 2: Enrich the ~74 that pass.** Cost: 74 × 10 = 740 credits for DM search.

**Step 3: Verify and draft.** Cost: ~30 sendable contacts at 25.7 credits each = ~770 credits.

**Total for the 250 already queued: ~1,510 provider credits, ~2,400 model calls, ~30 sendable contacts.**

### If 30 sendable is not enough

| Target sendable | Records needed | Provider credits | Model calls |
|----------------:|---------------:|-----------------:|------------:|
| 30 | 250 (already queued) | 784 | 2,458 |
| 50 | 410 | 1,287 | 4,030 |
| 100 | 821 | 2,578 | 8,070 |

### Recommendation

**Run the 250 already queued through qualify first.** It is free and will confirm whether the 40% ICP rejection rate holds on this batch (the purchased list skews micro-agencies). Then enrich whatever passes, at ~10 credits per record for DM search.

Do not ingest a second batch until the first 250 are through qualify. If the rejection rate is similar (~60%), a 410-record batch (250 already queued + 160 new) is the right size to reach 50 sendable contacts. A full 500 batch costs 1,568 credits and yields ~61 sendable.

The bottleneck is not credits (3.14 per record amortised) — it is the 8.2:1 input-to-output ratio of records processed per sendable contact, driven by the purchased list's skew toward companies below the client's 20-employee minimum.
