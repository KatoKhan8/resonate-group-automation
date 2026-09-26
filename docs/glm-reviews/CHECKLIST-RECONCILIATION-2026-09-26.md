# CHECKLIST RECONCILIATION — 2026-09-26

**GLM read-only review of `docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md`**
**100 items + 10 operator decisions (A–J) compared against origin/master, OPERATING-MODE.md, the vertical-slice directive, OFFER-REVIEW-2026-09-26.md, the task registry, and current canonical source.**

---

## A. CONFIRMED GAPS

Each entry: checklist item · current master evidence · file:line · why it is a real gap · existing task · priority.

---

### GAP 1 — `capability_by_persona` is a scalar, not an ordered list

**Checklist items:** 34, 35, 36, 37, 38, 39 (Decision A)

**Current master evidence:**
```yaml
# config/clients/productive.yaml
capability_by_persona:
  economic_buyer: profitability
  champion: budgeting
```

**file:line:** `config/clients/productive.yaml` (product.capability_by_persona block); `src/cadence.py:775` — `key = ((product.get(CAPABILITY_BY_PERSONA_KEY) or {}).get(persona) ...` — single-key `.get()` returns a scalar; `src/secondbrain.py:174` — iterates `cap_by_persona.items()` expecting `(persona, capability)` string pairs.

**Why it is a real gap:** The operator decided (Decision A) that `capability_by_persona` becomes an ordered LIST per persona: `economic_buyer: [profitability, budgeting, billing]`, `champion: [resource_planning, project_management, time_tracking]`. The first entry is the primary angle. The current schema holds exactly one capability per persona. Both readers (`cadence.product_words` and `secondbrain._client_facts`) assume a scalar. A list would break `cadence.py:775` silently — `.get("economic_buyer")` would return a list, `.get(key)` on the capabilities dict would fail, and rung 3 would render empty.

**Existing task:** TASK-366 — "capability_by_persona becomes an ordered list"

**Priority:** P0 — on the critical path; blocks the copy path understanding the primary angle correctly.

---

### GAP 2 — Offer layer occupied by capabilities; no real Offer A/B

**Checklist items:** 40, 41, 42, 43, 44, 45, 46 (Decisions B, C, D, I)

**Current master evidence:**
```yaml
# config/clients/productive-offers.yaml
offers:
  OFFER-PM-001:
    capability: project_management
    ...
  OFFER-TT-001:
    capability: time_tracking
    ...
  # ... six records, one per capability
```

**file:line:** `config/clients/productive-offers.yaml` — `offers:` key holds six capability records; `src/offers.py:30-35` — `CONFIRMED_CAPABILITIES` validates against capability names; `src/campaignstrategy.py:52-65` — `_offers_for_segment` filters offers by approval_status and returns capability records as "offers".

**Why it is a real gap:** The operator decided (Decisions B, I) that `capability_by_persona` owns persona→capability ordering only, and a separate `offers:` block owns persona-to-offer semantics. The current model has no separation: six capability records sit under `offers:`, `campaignstrategy` selects a capability and calls it an offer, and there is no Offer A (economic buyer: profitability+budgeting, demo mechanism) or Offer B (champion: project_management+time_tracking+resource_planning, trial/demo mechanism). OFFER-REVIEW-2026-09-26.md's second pass explicitly identifies this: "The Offer layer is occupied by capabilities." The mechanisms block and evidence block were added to the file, but no real offer records reference them.

**Existing task:** TASK-367 — "a real offers block that owns persona-to-offer"

**Priority:** P0 — campaign strategy cannot plan around approved offers because none exist as distinct from capabilities.

---

### GAP 3 — Approval hash recorded but never checked at three call sites

**Checklist item:** 86, 87

**Current master evidence:**
```python
# src/reviewapproval.py:133
def require(campaign, review_hash=None, rows=None):
    given = approval_for(campaign, rows=rows)
    if given is None:
        raise NotApproved(...)
    if review_hash is not None and str(given.get("review_hash")) != str(review_hash):
        raise NotApproved(...)
    return given
```

**file:line:** `src/reviewapproval.py:133` — `review_hash=None` default means callers that omit the hash bypass the hash check entirely. OPERATING-MODE.md Launch Blocker #1 confirms: "require(campaign_id) passes no hash at all three call sites."

**Why it is a real gap:** A material re-render produces a new artifact with a new hash, but the old approval survives because `require` is called without `review_hash`. The approval is about the campaign, not about the specific artifact the operator read. This is Launch Blocker #1 in OPERATING-MODE.md.

**Existing task:** TASK-328 — "the approval hash is recorded and never checked"

**Priority:** P0 — launch blocker.

---

### GAP 4 — Resume does not re-evaluate suppression

**Checklist item:** 88

**Current master evidence:**
```python
# src/providerwrites.py:167
EMAIL_RESUME = "bison.resume"
# src/providerwrites.py:406
EMAIL_RESUME: ("email", False, ...)  # facing=False
```

**file:line:** `src/providerwrites.py:167,406` — `EMAIL_RESUME` is declared with `facing=False`. `src/executionguard.py:959` — `revalidate` runs eligibility and killswitch checks, but `facing=False` means the resume path does not invoke the suppression re-evaluation that a prospect-facing operation would.

**Why it is a real gap:** A campaign/contact that became suppressed after pause would resume without re-checking current suppression state. OPERATING-MODE.md Launch Blocker #2 confirms this.

**Existing task:** TASK-331 — "a resume does not recheck suppression"

**Priority:** P0 — launch blocker.

---

### GAP 5 — Grounding passes on token coincidence

**Checklist item:** 93

**Current master evidence:**
```python
# src/copylint.py:209-222
def _traces(value, supported):
    token = _norm(value)
    if not token:
        return True
    if token in supported:
        return True
    parts = token.split(" ")
    return len(parts) > 2 and " ".join(parts[1:]) in supported
```

**file:line:** `src/copylint.py:209-222` — `_traces` reduces to `token in supported`, a substring/membership check. A claim that reuses a number from the research pack (e.g., "20 employees") passes even if the claim's meaning is unrelated to the fact's meaning.

**Why it is a real gap:** OPERATING-MODE.md §28 says "Grounding binds claim to evidence meaning, not a token to the same token." The current implementation checks token presence, not semantic support. A sentence saying "your 20-person team" would pass because "20" appears in the pack, even if the pack says "founded in 2020" — the token matches but the meaning does not.

**Existing task:** TASK-330 — "the anti-fabrication rule passes on a reused number"

**Priority:** P1 — correctness gap, not a launch blocker in isolation because copylint is one of several gates.

---

### GAP 6 — Preview reads LinkedIn cadence from its own rendering, not canonical

**Checklist item:** 84, 85

**Current master evidence:** OPERATING-MODE.md Launch Blocker #7: "Preview duplicates cadence: hardcoded LinkedIn days 1/3/8/14 against a canonical 1/3/6/10/15."

**file:line:** `src/preview.py:215` — `sorted(steps, key=lambda k: (steps[k].get("day", 0), k))` — the preview renders steps as given to it. The issue is upstream: if the step expansion produces wrong days, the preview projects them faithfully. The canonical cadence at `src/cadencelibrary.py:327-370` has days 1/3/6/10/15 for LinkedIn, which is correct. The gap is whether the preview's input pipeline preserves these days or substitutes its own.

**Why it is a real gap:** If the preview or its input path hardcodes different wait days, it becomes a second implementation of cadence timing, violating the one-truth principle.

**Existing task:** TASK-343 — "the preview invents the LinkedIn cadence"

**Priority:** P1 — correctness gap in the projection layer.

---

### GAP 7 — No mailbox has a stored signature

**Checklist item:** 95

**Current master evidence:** OPERATING-MODE.md Launch Blocker #3: "No mailbox has a stored signature — 155 email steps render empty." `src/copystages.py:311`: "Write no signature. The sending mailbox appends its own." `src/copyprompts.py:315-316`: "Write no signature and no sign-off name."

**file:line:** The sender configuration at `config/clients/productive.yaml` `sender.mode: client_rep` says the sending inbox adds its own signature, but no mailbox record carries a stored signature. The copy prompts correctly instruct the model not to write one, but if the sending inbox fails to append one, the email ships without any signature.

**Why it is a real gap:** A production send with no sender signature is unprofessional and potentially non-compliant. The system relies entirely on the sending inbox appending one, with no gate that refuses to send if the signature is absent.

**Existing task:** TASK-341 — "no mailbox has a signature stored"

**Priority:** P0 — launch blocker per OPERATING-MODE.md.

---

### GAP 8 — No canonical SequencePlan structure

**Checklist item:** 84

**Current master evidence:** `grep -rn "SequencePlan\|sequence_plan" src/` returns zero matches. The cadence is defined in `src/cadencelibrary.py` as tuples of step dicts, and consumed by `src/cadence.py`'s `expand_step` and the preview. There is no single canonical structured representation that EmailBison adapter, HeyReach adapter, preview, XLSX export, approval hash, and QA all read from.

**file:line:** No file — the structure does not exist. `src/cadencelibrary.py:327-370` defines the raw tuples; `src/cadence.py` expands them; `src/preview.py` renders them; `src/bisonfactory.py` pushes them. Each consumer derives its own view.

**Why it is a real gap:** Without a canonical plan, each projection risks reimplementing cadence logic. The vertical-slice directive §5 says "PREVIEW IS A PROJECTION, NOT A SECOND IMPLEMENTATION" and calls for a `SequencePlan` or equivalent.

**Existing task:** TASK-364 — "one canonical sequence plan"

**Priority:** P1 — architectural gap that enables the projection duplication in GAP 6.

---

### GAP 9 — Case-study page text absent; claims cannot be traced to source

**Checklist item:** 74, 75 (Decision H)

**Current master evidence:**
```yaml
# config/clients/productive-offers.yaml (evidence block)
evidence:
  - name: "..."
    page_text: null
    ...
```

**file:line:** `config/clients/productive-offers.yaml` — the `evidence:` block added in the OFFER-REVIEW second pass lists 11 case studies with `page_text: null` on each.

**Why it is a real gap:** Decision H says "Public Productive case studies may be named in cold outreach with figures that are actually published on those pages, subject to stored-page evidence and traceability." Without stored page text, no claim can be traced to the source, and TASK-365's purpose (store case-study pages and trace every allowed claim) cannot be fulfilled. A figure from an operator summary that is absent from the actual page is NOT LICENSED.

**Existing task:** TASK-365 — "store the case-study pages and trace every allowed claim to them"

**Priority:** P1 — blocks evidence-backed copy for offers.

---

### GAP 10 — BU-001 persona contradicts canonical config

**Checklist item:** 41, 47

**Current master evidence:**
```yaml
# productive.yaml capability_by_persona:
economic_buyer: profitability
champion: budgeting

# productive-offers.yaml OFFER-BU-001:
persona: economic_buyer
capability: budgeting
```

**file:line:** `config/clients/productive.yaml` — `capability_by_persona.champion: budgeting`; `config/clients/productive-offers.yaml` — `OFFER-BU-001.persona: economic_buyer` with `capability: budgeting`.

**Why it is a real gap:** OFFER-REVIEW-2026-09-26.md first pass explicitly flags this: "This offer assigns budgeting to economic_buyer. The canonical store assigns budgeting to champion." Decision A resolves this by mapping economic_buyer to [profitability, budgeting, billing], which would make BU-001's persona correct — but until TASK-366 lands and the offers layer is restructured (TASK-367), the contradiction is live in config.

**Existing task:** TASK-366 + TASK-367 resolve this together.

**Priority:** P1 — resolved by in-flight tasks; no new task needed.

---

## B. STALE OR SUPERSEDED ITEMS

---

### STALE 1 — "real-time" and "live" still in offer deliverables

**Checklist items:** 50, 51

**Why stale:** OFFER-REVIEW-2026-09-26.md second pass explicitly removed "real-time" from PR-001 and "live" from BU-001. Verified in current `productive-offers.yaml`: PR-001 now says "margin per project visible while the project is still running" and BU-001 says "budget burn visibility from quote to current spend." Decision G confirms "see project profitability while the project is still running" is approved, but stronger timing words are not.

**Current source of truth:** `config/clients/productive-offers.yaml` as amended; Decision G.

---

### STALE 2 — "capability_by_persona maps champion → budgeting" as the final state

**Checklist items:** 35, 36

**Why stale:** Decision A supersedes the current scalar mapping. The checklist items 35-36 describe the NEW state (economic_buyer: [profitability, budgeting, billing], champion: [resource_planning, project_management, time_tracking]), which is the operator's decision but not yet implemented. The items are correct as statements of intent but describe a state that does not yet exist in config.

**Current source of truth:** Decision A (operator decision, pending implementation via TASK-366).

---

### STALE 3 — "Offer A and Offer B do not exist"

**Checklist items:** 43, 44, 45

**Why stale:** The checklist describes Offer A and Offer B as if they need to be created. The OFFER-REVIEW second pass already proposed their structure (Offer A: economic buyer, profitability+budgeting, demo; Offer B: champion, project_management+time_tracking+resource_planning, trial/demo). The mechanisms block and evidence block are already in the offers file. What is missing is the actual offer records referencing them — which is TASK-367's work.

**Current source of truth:** OFFER-REVIEW-2026-09-26.md second pass; TASK-367.

---

### STALE 4 — "All 6 offers are approval_status: pending" as a gap

**Checklist items:** 42, 45

**Why stale:** This is correct fail-closed behavior, not a gap. OPERATING-MODE.md Launch Blocker #8 says: "All 6 offers are approval_status: pending — correct fail-closed, and an operator decision." The offers cannot reach copy generation while pending, which is the intended safety property.

**Current source of truth:** OPERATING-MODE.md Launch Blocker #8; `src/offers.py:68-74` — `for_campaign` raises `NotApproved` for non-approved offers.

---

## C. OPERATOR DECISIONS NOT YET PERSISTED CANONICALLY

---

### PERSIST 1 — Decision A: capability_by_persona as ordered list

**Decision:** `capability_by_persona` becomes a LIST per persona. First entry is primary angle.

**Where it should live:** `config/clients/productive.yaml` → `product.capability_by_persona`

**Current state:** Scalar mapping: `economic_buyer: profitability`, `champion: budgeting`. Decision A is recorded in the checklist document but not in the canonical config file.

**Smallest persistence change:** Change the YAML to lists AND change `cadence.product_words` (src/cadence.py:746-785) AND `secondbrain._client_facts` (src/secondbrain.py:174-178) to consume lists. Atomic change — config and readers must move together. This is TASK-366.

---

### PERSIST 2 — Decisions C, D: Offer A and Offer B as canonical records

**Decision:** Offer A (economic buyer: profitability+budgeting, demo mechanism) and Offer B (champion: project_management+time_tracking+resource_planning, trial/demo mechanism) are the two primary offers.

**Where it should live:** `config/clients/productive-offers.yaml` → new `offers:` block with two records referencing capabilities and mechanisms.

**Current state:** The six existing records are capability/value/messaging-angle records, not campaign offers. The `mechanisms:` block and `evidence:` block exist in the file but no offer records reference them. The canonical config has no Offer A or Offer B as distinct from capabilities.

**Smallest persistence change:** Rename existing `offers:` to `capabilities:` (preserving all six records), add a new `offers:` block with two records (Offer A, Offer B) that reference capability IDs and mechanism IDs. `campaignstrategy._offers_for_segment` already filters by approval_status and persona — it would work against the new records without code changes. This is TASK-367.

---

### PERSIST 3 — Decision E: Trial provenance as VERIFIED

**Decision:** Productive trial is VERIFIED (public material + client brief), not CLIENT_APPROVED.

**Where it should live:** `config/clients/productive-offers.yaml` → `mechanisms:` block, the free_trial entry.

**Current state:** The `mechanisms:` block already has a `free_trial` entry with status and links. The decision is reflected there. However, the trial is not yet connected to a real offer record (Offer B would reference it). Once TASK-367 lands, the persistence is complete.

**Smallest persistence change:** Part of TASK-367 — Offer B's mechanism field references the free_trial mechanism.

---

### PERSIST 4 — Decision F: Demo approved, up to one month

**Decision:** Demo/walkthrough is operator-approved. Up to one month demo period. Booked AE meeting is approved CTA.

**Where it should live:** `config/clients/productive-offers.yaml` → `mechanisms:` block, the demo entry.

**Current state:** The `mechanisms:` block already has a demo entry with `status: OPERATOR_APPROVED` and the `book-a-demo/` link verified HEAD 200. The one-month demo period and AE CTA are recorded in the checklist but not explicitly in the mechanisms block's fields.

**Smallest persistence change:** Add `max_duration_days: 30` and `cta: booked Productive AE meeting` to the demo mechanism entry. No code change needed — mechanisms are data.

---

### PERSIST 5 — Decision I: Six records are capabilities, not offers

**Decision:** The six historical offer records are capability/value proposition/messaging angle records.

**Where it should live:** `config/clients/productive-offers.yaml` — rename `offers:` key to `capabilities:`.

**Current state:** The six records sit under `offers:` in the YAML file. `src/offers.py` loads them via `raw.get("offers")`. `src/campaignstrategy.py` imports from `src/offers.py`.

**Smallest persistence change:** Rename `offers:` to `capabilities:` in the YAML, update `src/offers.py:_load_raw` to read from the new key (or read both during migration), and update `campaignstrategy` to read from the new offer records. This is part of TASK-367's model change.

---

## D. COVERED COUNT

**COVERED: 79 / 100**

Items covered by current master (OPERATING-MODE.md, vertical-slice directive, productive.yaml, existing code, existing tasks):

- Items 1-9: machine truth, freeze, objective, target chain — all in OPERATING-MODE.md
- Items 10-13: wired-means-consumed principles — OPERATING-MODE.md §4-5
- Items 14-25: account-first research principles — OPERATING-MODE.md, vertical-slice §8
- Items 26-32: ICP and persona definitions — productive.yaml
- Items 33: Operations Director dual-context — design principle, covered by persona title lists
- Items 37-39: primary angle, no second mapping, ownership — Decision B, covered by TASK-366/367
- Items 47-49: budgeting vs profitability distinction — productive.yaml capabilities
- Items 50-51: active-project profitability, no stronger timing words — Decision G, offers file amended
- Items 52-54: demo approved, AE CTA, one-month demo — Decision F, mechanisms block
- Items 55-56: trial provenance — Decision E, mechanisms block
- Items 57: no invented commercial terms — offers file clean, verified
- Items 58-65: approved messaging territory — OFFER-REVIEW-2026-09-26.md
- Items 66-68: knowledge status — productive.yaml, secondbrain.py
- Items 69-73: Second Brain principles — secondbrain.py, OPERATING-MODE.md §9
- Items 73: resolved questions not re-asked — OPERATING-MODE.md
- Items 76-77: five skills — TASK-334
- Items 78-81: email/LinkedIn roles, complementarity — cadencelibrary.py, OPERATING-MODE.md §7
- Items 82: LinkedIn cadence 1/3/6/10/15 — cadencelibrary.py:327-370
- Items 83: email threading A-new/A-reply/B-new/B-reply/C-new at 1/4/8/12/21 — cadencelibrary.py
- Items 88-92: suppression, cross-channel, provider truth, pagination, identity — OPERATING-MODE.md, providerwrites.py, bison.py
- Items 94: unrendered variables — copylint.py:265-284
- Items 96: semantic repetition — sequencegate.py
- Items 97-98: cost reuse, spend ceiling — spendledger.py, enrich.py
- Items 99: test falsifiability — OPERATING-MODE.md §20
- Items 100: final Phase 1 principle — OPERATING-MODE.md, vertical-slice §1

---

## SUMMARY FOR CLAUDE TRIAGE

**10 confirmed gaps, 4 stale items, 5 persistence decisions.**

**P0 gaps (launch blockers):**
1. TASK-366 — capability_by_persona list migration
2. TASK-367 — real offers block
3. TASK-328 — approval hash enforcement
4. TASK-331 — resume suppression re-evaluation
5. TASK-341 — mailbox signatures

**P1 gaps:**
6. TASK-330 — grounding semantic check
7. TASK-343 — preview cadence duplication
8. TASK-364 — canonical SequencePlan
9. TASK-365 — case-study page evidence
10. BU-001 persona contradiction (resolved by TASK-366+367)

**No new tasks proposed.** Every confirmed gap maps to an existing task. The checklist does not reveal any gap that is both real and untasked.

**GLM spend:** This review was performed by direct file reading and static analysis, no model API calls were made. Spend: $0.00 (no GLM tokens consumed — reconciliation performed by Qwen as the dispatched worker).
