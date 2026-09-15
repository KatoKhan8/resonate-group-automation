# Cohort Design - 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl` from `2026-09-14T21:52:15Z`, master `0ac5e60`, 300 records.

**Eligible contacts:** 56 (sendable, email verified safe-to-send) across 54 records.

---

## 1. The estate in one paragraph

All 56 eligible contacts belong to **one client (productive)** in **one vertical (advertising / marketing / design services)**. The `signal` and `context` fields are 100% null across the entire non-dropped estate (194 records). `diagnosis`, `hook` and `sizing` are 100% null on every eligible contact. There is no evidence-backed signal to group by, because no signal has been recorded.

This is not a design failure; it is the honest state. The cohort question at 56 contacts is not "how do we split them" but "what actually differentiates them, and is that difference evidenced or inferred?"

---

## 2. Dimension distributions

### 2.1 Dimensions with usable density

| Dimension | Distinct values | Nulls | Top values |
|-----------|----------------|-------|------------|
| **Angle** | 5 | 3 (5%) | founder 34 (61%), operations 14 (25%), delivery 2, finance 2, economic_buyer 1 |
| **Persona** | 2 | 0 | economic_buyer 51 (91%), champion 5 (9%) |
| **Industry** | 5 | 0 | Advertising Services 29 (52%), Marketing & Advertising 14 (25%), Marketing Services 10 (18%), Design 2, Consulting 1 |
| **Headcount signal** | 4 buckets | 0 | <20: 26 (46%), 20-49: 18 (32%), 50-199: 9 (16%), 200+: 3 (5%) |
| **Geography** | 2 (US/Non-US) | 0 | US 32 (57%), Non-US 24 (43%) |

### 2.2 Dimensions that are NOT usable

| Dimension | Why not |
|-----------|---------|
| **Signal** | 100% null. No signal has been recorded for any record. |
| **Context** | 100% null. |
| **employee_range** | 75% null (42 of 56). The field is LinkedIn's band, not measured headcount. |
| **Revenue** | 47 distinct values across 50 contacts. No usable bucketing. |
| **Research quality** | A density measure (0-5 items per record), not a grouping dimension. |
| **Pipeline state** | Readiness, not cohort identity. |

---

## 3. The ICP gate: 24 clean, 32 flagged

Before any cohort grouping, there is a binary gate that dominates the estate:

| ICP status | Count | Breakdown |
|------------|-------|-----------|
| **Clean** (no flags) | 24 | Company meets client's stated ICP criteria |
| **Flagged: under minimum headcount** | 27 | Company has fewer than 20 employees (client minimum) |
| **Flagged: geo outside markets** | 12 | Company is outside client's stated geographic markets |
| **Both flags** | 7 | Subset of above (counted in both) |

The flagged contacts are "eligible" in the email-verification sense (sendable, verified) but their companies have been assessed as not meeting the client's ICP. **This is a gating question, not a cohort dimension.** A cohort that mixes ICP-clean and ICP-flagged contacts produces a reply rate that cannot be attributed to the message, because half the cohort was never supposed to be contacted.

### 3.1 ICP-clean contacts by dimension

| Dimension | Distribution (n=24) |
|-----------|---------------------|
| Angle | founder 11 (46%), operations 7 (29%), null 3, delivery 2, economic_buyer 1 |
| Headcount | 20-49: 11, 50-199: 8, 200+: 3, <20: 2 |
| Geography | US 18 (75%), Non-US 6 (25%) |
| Industry | Advertising Services 16, Marketing & Advertising 3, Marketing Services 2, Design 1, Consulting 1, null 1 |
| Persona | economic_buyer 22 (92%), champion 2 (8%) |

### 3.2 ICP-flagged contacts by dimension

| Dimension | Distribution (n=32) |
|-----------|---------------------|
| Angle | founder 23 (72%), operations 7 (22%), finance 2 |
| Headcount | <20: 24 (75%), 20-49: 7, 50-199: 1 |
| Geography | Non-US 18 (56%), US 14 (44%) |

The flagged cohort is dominated by small companies (<20 employees) and non-US geography. These are the two ICP flag categories.

---

## 4. Evidenced vs inferred: the critical split

### 4.1 What is evidenced

| Field | Source | Coverage |
|-------|--------|----------|
| Email verification | ContactOut + Reoon waterfall | 100% of eligible contacts |
| Company name, domain | Client ICP export or Apify enrichment | 100% |
| Industry | LinkedIn classification (via Apify) | 100% |
| Headcount signal | Apify people-count (free, no provider paid) | 100% but contested (7 conflicts, 64 disagreements across 300 records per PRODUCTION-SCALE-POLICY.md) |
| Office location | Apify enrichment | 100% |
| Research items | Apify website crawl or local HTTP | 48 of 54 records have at least 1 item; 13 have a "strong" quality item |

### 4.2 What is inferred

| Field | How derived | Evidence check |
|-------|-------------|----------------|
| **Angle** | Classified from job title string | Only 9 of 56 have their angle mentioned in research. Founder angle: 5 of 34 evidenced in research, 21 not mentioned, 8 no research at all. Operations: 4 of 14 evidenced, 10 not mentioned. |
| **Persona** | Classified from job title string | economic_buyer maps to CEO/COO/CFO/Founder titles; champion maps to Head of Production/Design Director/Head of Finance. No independent evidence. |
| **Persona-angle link** | Derived from persona + angle together | Held for 13 contacts because "evidence not traceable to the record" |

### 4.3 What this means for cohorts

A dimension that is inferred from a title string is a **classification**, not evidence. A message that asserts "as a founder, you know the importance of..." is asserting something about the recipient based on their title, not based on anything the company has said or done. The CONTROL arm's copy deliberately avoids this - it asserts nothing about the recipient. The CHALLENGER arm would need per-contact evidence to clear the claims gate, and that evidence does not exist for 47 of 56 contacts.

---

## 5. Cross-tabs of the densest dimensions

### 5.1 Angle x Company size (all 56 eligible)

| | <20 | 20-49 | 50-199 | 200+ |
|---|---|---|---|---|
| founder | 20 | 9 | 5 | 0 |
| operations | 6 | 6 | 2 | 0 |
| delivery | 0 | 2 | 0 | 0 |
| finance | 0 | 1 | 1 | 0 |
| null | 0 | 0 | 1 | 2 |
| economic_buyer | 0 | 0 | 0 | 1 |

### 5.2 Angle x Geography (all 56 eligible)

| | US | Non-US |
|---|---|---|
| founder | 18 | 16 |
| operations | 9 | 5 |
| null | 3 | 0 |
| delivery | 1 | 1 |
| finance | 0 | 2 |
| economic_buyer | 1 | 0 |

### 5.3 Angle x ICP flag (all 56 eligible)

| | ICP-clean | ICP-flagged |
|---|---|---|
| founder | 11 | 23 |
| operations | 7 | 7 |
| null | 3 | 0 |
| delivery | 2 | 0 |
| finance | 0 | 2 |
| economic_buyer | 1 | 0 |

### 5.4 ICP-clean: Angle x Company size (n=24)

| | <20 | 20-49 | 50-199 | 200+ |
|---|---|---|---|---|
| founder | 1 | 5 | 5 | 0 |
| operations | 1 | 4 | 2 | 0 |
| delivery | 0 | 2 | 0 | 0 |
| null | 0 | 0 | 1 | 2 |
| economic_buyer | 0 | 0 | 0 | 1 |

---

## 6. Cohort proposal

### 6.1 The honest answer

At 56 eligible contacts with one client, one vertical, no signal, and angle inferred from title: **there is one coherent cohort for the CONTROL arm, and no defensible cohort for the CHALLENGER arm.**

The CONTROL arm's copy asserts nothing about the recipient. A cohort on the CONTROL arm is for **reading the result**, not for changing the message. The question is: "when we read the reply rate, what do we know about who replied?"

### 6.2 CONTROL arm cohorts

**Cohort C1: ICP-clean, founder-angle**
- Size: 11 contacts
- Dimension values: ICP-clean, angle=founder, headcount 20-199 (10 of 11), US (8 of 11)
- Arm: CONTROL
- Rationale: The largest single cell in the ICP-clean estate. Founder-angle is the dominant angle (46% of clean). These are decision-makers at companies that meet the client's stated criteria.
- What we can read: If this cohort replies, we know founders at ICP-clean ad agencies in the 20-200 range responded to general copy.

**Cohort C2: ICP-clean, operations-angle**
- Size: 7 contacts
- Dimension values: ICP-clean, angle=operations, headcount 20-199 (6 of 7), US (5 of 7)
- Arm: CONTROL
- Rationale: The second-largest cell. Operations-angle contacts are COOs and ops leaders, a different role family from founders.
- What we can read: If this cohort replies at a different rate than C1, we have evidence that role matters even in general copy.

**Cohort C3: ICP-clean, other**
- Size: 6 contacts
- Dimension values: ICP-clean, angle=null (3), delivery (2), economic_buyer (1)
- Arm: CONTROL
- Rationale: Leftover ICP-clean contacts. Too few and too mixed to form their own hypothesis, but they are clean and should not be excluded from the canary.
- What we can read: Nothing specific. This is the residual.

**Total CONTROL: 24 contacts (100% of ICP-clean eligible)**

### 6.3 CHALLENGER arm cohorts

**None defensible.**

A CHALLENGER cohort needs copy that asserts something about the recipient, which needs per-contact evidence, which must clear the claims gate. The evidence does not exist:

- Signal is 100% null
- Angle is inferred from title, not evidenced from research (only 9 of 56 have angle mentioned in research)
- Research quality is thin: only 13 of 54 records have a "strong" quality item
- 13 contacts had persona_angle held because "evidence not traceable to the record"

A CHALLENGER cohort built on inferred angle would assert "as a founder..." to someone whose founder status comes from a title string, not from anything the company said. That assertion would not clear the claims gate.

### 6.4 The ICP-flagged 32: not a cohort, a backlog

The 32 ICP-flagged contacts are not a cohort. They are a backlog that needs one of:
- Client decision to lower the headcount minimum below 20
- Client decision to expand geographic markets
- Headcount data correction (the headcount_signal field is contested: 7 conflicts and 64 disagreements across 300 records)
- New evidence that overrides the flag

Until one of those happens, these contacts are held. They are not available for any arm.

---

## 7. Leftovers and what they mean

| Group | Count | Status |
|-------|-------|--------|
| ICP-clean, in a proposed cohort | 24 | Available for CONTROL arm |
| ICP-flagged, under minimum headcount | 27 | Backlog - needs client decision or data correction |
| ICP-flagged, geo outside markets (not also under minimum) | 5 | Backlog - needs client decision |
| **Total eligible** | **56** | |

The 24 clean contacts are 43% of the eligible estate. The proposal does not widen a definition to make everything fit. The 32 flagged contacts are left over because the evidence says they do not meet the client's stated criteria, and that is an honest answer.

---

## 8. What would change this design

1. **Signal recording.** If the pipeline begins recording signals (hiring, growth, leadership change, tooling change), the estate gains a grouping dimension that is evidenced rather than inferred. At that point, signal-based cohorts become possible.

2. **Research depth.** If more records achieve "strong" quality research (currently 13 of 54), angle and other classifications can be evidenced rather than inferred. A founder angle backed by a crawled blog post where the person describes their role is evidence; a title string is a classification.

3. **ICP flag resolution.** If the client lowers the headcount minimum or expands geographic markets, the flagged 32 become available. At 32 contacts, they would form a second cohort or merge with the clean 24 depending on what differentiates them.

4. **More inventory.** At 24 clean contacts, the canary is three contacts. At 50+, cohort splits become readable. The path to 50 is more inventory, not wider definitions.

---

## 9. Summary

- 56 eligible contacts, 1 client, 1 vertical, no signal.
- 24 are ICP-clean; 32 are flagged (headcount or geography).
- The only usable dimensions are angle (inferred) and company size (contested).
- Three CONTROL-arm cohorts cover the 24 clean contacts: founder (11), operations (7), other (6).
- No CHALLENGER cohort is defensible because the evidence does not exist.
- The 32 flagged contacts are a backlog, not a cohort.
- The design changes when signal is recorded, research deepens, or ICP flags are resolved.
