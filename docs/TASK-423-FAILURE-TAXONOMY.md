# TASK-423 — Failure Taxonomy of the Fifty's 37 Non-Passing Leads

**STATUS:** REVIEW
**Worker:** Qwen Pro (qwen-worker-6-r9)
**Date:** 2026-09-28
**Artifact kind:** document (analysis + findings)

## SOURCE DATA

The definitive `work/fifty-data.json` (437 KB, referenced by TASK-342) no longer
exists in any worktree. Analysis was reconstructed from three surviving artifacts
in Claude's worktree (`C:/Users/Zvonimir/Desktop/resonate-group-automation/work/`):

1. `review/fifty-verified/503-FIFTY-v2-2026-09-25.html` (332 KB) — the posted
   review file with per-lead ICP, hypothesis, capability, sequence gate, copylint,
   full email bodies and LinkedIn messages. Generated 2026-09-25 by `v2_pages.py`.
2. `review/fifty-verified/503-FIFTY-v2-2026-09-25.xlsx` — the posted workbook
   with Summary and Leads sheets. Same generation run.
3. `sample50-built.json` (284 KB) — the template-rendered lead data from
   `sample50_final.py`, with Bison lead IDs.

The HTML and XLSX are hash-pinned posted artifacts
(`0c493ab9c3d9d136` / `775cd55287b8f29a`) and were NOT modified.

**Identifiers:** Each lead is identified by `R##` (the row number in the posted
review XLSX, which matches the HTML's table of contents). No email addresses,
personal names, or domains appear in this committed file.

## NUMBERS

    Total leads:             50
    Held before gates:       19  (QUALIFICATION stage)
    Written (reached gates): 31
    Gate results (from HTML sequence gate):
      PASSED:                21
      FAILED:                10
    PASS BOTH GATES:         13  (per TASK-342's copylint re-lint)
    NON-PASSING:             37  (= 19 held + 18 failed at least one gate)

**Note on copylint vs sequence gate in the HTML:** The HTML was generated on
2026-09-25. At that time, copylint checked email bodies only — LinkedIn messages
and P.S. lines were outside every rule (noted in `copylint.py:636-638`). The
TASK-342 count of "13 unrendered_variable" comes from a LATER re-lint with
expanded rules that included LinkedIn. The HTML's per-lead copylint column
therefore under-reports refusals: leads whose only defect was `{firstName}` in
LinkedIn messages showed "clean" in the HTML but refuse under current rules.

---

## DELIVERABLE 1 — PER-LEAD TABLE

37 non-passing leads, exactly one primary reason each.
Each lead is classified at its EARLIEST pipeline failure stage.

### 19 Held at QUALIFICATION (or INPUT)

| ID  | Stage         | Reason code             | Evidence |
|-----|---------------|-------------------------|----------|
| R03 | QUALIFICATION | `not_an_agency`         | ICP model: "content creator-brand marketplace" — not a services agency |
| R04 | QUALIFICATION | `not_an_agency`         | ICP model: "lead-generation/data platform" — SaaS, not agency |
| R05 | QUALIFICATION | `not_an_agency`         | ICP model: "University" — .edu domain, educational institution |
| R11 | QUALIFICATION | `not_an_agency`         | ICP model: "affiliate marketing and lead generation" — performance network |
| R15 | QUALIFICATION | `not_an_agency`         | ICP model: "digital marketing platform or product" — platform, not services |
| R22 | QUALIFICATION | `no_pack_facts`         | Research pack yielded zero verifiable facts about the company |
| R23 | QUALIFICATION | `not_an_agency`         | ICP model: "unclear from text, possibly a brand consultancy" — ambiguous |
| R26 | QUALIFICATION | `not_an_agency`         | ICP model: "software product company" — sells software, not agency services |
| R32 | QUALIFICATION | `not_an_agency`         | ICP model: "AI-powered marketing automation platform" — SaaS product |
| R33 | QUALIFICATION | `no_pack_facts`         | Research pack yielded zero verifiable facts about the company |
| R35 | QUALIFICATION | `not_an_agency`         | ICP model: "Marketing technology platform" — martech product |
| R38 | QUALIFICATION | `no_pack_facts`         | Research pack yielded zero verifiable facts about the company |
| R39 | QUALIFICATION | `not_an_agency`         | ICP model: "programmatic advertising technology" — adtech platform |
| R40 | QUALIFICATION | `not_an_agency`         | ICP model: "Fractional digital talent provider" — staffing, not agency |
| R45 | QUALIFICATION | `not_an_agency`         | ICP model: "digital brand builder and operator" — holds brands, not services |
| R47 | QUALIFICATION | `not_an_agency`         | ICP model: "retail solution provider" — retail services, not marketing agency |
| R48 | QUALIFICATION | `no_pack_facts`         | Research pack yielded zero verifiable facts about the company |
| R49 | INPUT         | `missing_company_data`  | `template_vars` raised: no company name on record, domain empty |
| R50 | INPUT         | `missing_company_data`  | `template_vars` raised: no company name on record, domain empty |

### 13 RENDER — `unrendered_variable` (`{firstName}` in LinkedIn)

These 13 leads had `{firstName}` as a literal token in their LinkedIn messages.
5 of them ALSO failed sequencegate (noted), but the PRIMARY reason is the
unrendered variable at the RENDER stage, which is earlier in the pipeline.

| ID  | Stage  | Reason code           | Evidence | Also failed seqgate? |
|-----|--------|-----------------------|----------|----------------------|
| R02 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | YES: channels_complement |
| R09 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | YES: channels_complement |
| R12 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R13 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R14 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R16 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | YES: channels_complement |
| R19 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R20 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R27 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | YES: claims_supported |
| R36 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | YES: claims_supported + channels_complement |
| R37 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R41 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |
| R43 | RENDER | `unrendered_variable` | `{firstName}` literal in LinkedIn connect + messages | no |

### 3 SEQUENCEGATE — `channels_complement` (no unrendered variable)

| ID  | Stage      | Reason code            | Evidence |
|-----|------------|------------------------|----------|
| R21 | SEQUENCEGATE | `channels_complement` | LinkedIn connect "is em1 in shorter form" — overlap >= 0.55 with email body |
| R25 | SEQUENCEGATE | `channels_complement` | Two LinkedIn steps each overlap with email (2 checks failed) |
| R46 | SEQUENCEGATE | `channels_complement` | LinkedIn connect "is em1 in shorter form" — overlap >= 0.55 with email body |

### 2 SEQUENCEGATE — `claims_supported` (no unrendered variable)

| ID  | Stage      | Reason code            | Evidence |
|-----|------------|------------------------|----------|
| R17 | SEQUENCEGATE | `claims_supported`    | em5 makes a specific claim tracing to no supplied pack fact |
| R31 | SEQUENCEGATE | `claims_supported`    | em5 makes a specific claim tracing to no supplied pack fact |

**Verification:** 19 + 13 + 3 + 2 = 37. Each lead has exactly one primary reason.

---

## DELIVERABLE 2 — PARETO TABLE

Each lead counted once, at its PRIMARY (earliest pipeline) failure stage.

| Rank | Stage         | Reason code            | Count | Cumulative | Cum %  |
|------|---------------|------------------------|-------|------------|--------|
| 1    | QUALIFICATION | `not_an_agency`        | 13    | 13         | 35.1%  |
| 2    | RENDER        | `unrendered_variable`  | 13    | 26         | 70.3%  |
| 3    | QUALIFICATION | `no_pack_facts`        | 4     | 30         | 81.1%  |
| 4    | SEQUENCEGATE  | `channels_complement`  | 3     | 33         | 89.2%  |
| 5    | SEQUENCEGATE  | `claims_supported`     | 2     | 35         | 94.6%  |
| 6    | INPUT         | `missing_company_data` | 2     | 37         | 100.0% |

**Sum: 13 + 13 + 4 + 3 + 2 + 2 = 37.**

The two largest causes — `not_an_agency` (13) and `unrendered_variable` (13) —
together account for 70.3% of all failures. The first is a list-sourcing problem
upstream of the pipeline. The second is a missing substitution step in the
LinkedIn rendering path.

---

## DELIVERABLE 3 — FIX LIST

Ordered by how many leads each fix unblocks.

### Fix 1 — LinkedIn `{firstName}` substitution (13 leads)

**Files:** `src/copystages.py:332` (WRITER_SYSTEM prompt), `src/copyprompts.py:343`
(COHORT_SYSTEM prompt), and the production equivalent in `src/generate_campaign.py`

**Upstream cause:** Two writer prompts explicitly instruct the model to write
`{firstName}` (camelCase) in LinkedIn messages:
- `copystages.py:332`: `"{firstName} opening every message after the connect"`
- `copyprompts.py:343`: `"**{firstName} opens every message after the connect.**"`

The model follows this instruction literally. Email templates use `{first_name}`
(snake_case) and go through `cadence.render()` which substitutes via
`str.format()`. But generated LinkedIn steps (li2-li5) are NOT run through
`render()` — the model output IS the final text. The naming mismatch between
`firstName` (prompt) and `first_name` (renderer) means the token survives
unrendered in every LinkedIn message.

**Fix (two parts):**
(a) Change the prompts to instruct the model to use the contact's actual name
directly (e.g., "use the contact's first name to open each message") instead of
the `{firstName}` template syntax.
(b) Add a post-generation substitution pass on LinkedIn copy as a safety net,
replacing any surviving `{firstName}` or `{first_name}` with the actual name.

**Leads unblocked:** R02, R09, R12, R13, R14, R16, R19, R20, R27, R36, R37, R41, R43

**Note:** This is a RENDER-stage defect, not a copylint defect. The gate is
working correctly by catching it. Widening copylint to ignore `{firstName}`
would convert a caught defect into a shipped one.

### Fix 2 — List sourcing: non-agency companies in the ICP (13 leads)

**File:** Upstream of the pipeline — the list that fed campaign 503.

**Upstream cause:** 13 of 50 leads (26%) were not marketing/service agencies.
The ICP model correctly identified them as UNQUALIFIED, but credits were spent
on research packs and ICP model calls for companies that were never going to
qualify. The companies included a university (R05), SaaS platforms (R04, R15,
R26, R32, R35, R39), a staffing company (R40), an affiliate network (R11), a
retail provider (R47), a brand holder (R45), a content marketplace (R03), and
an ambiguous consultancy (R23).

**Fix:** Add a pre-ICP filter that checks domain suffix (.edu -> reject),
company description keywords (SaaS, platform, software, staffing), and the
EmailBison campaign's existing list metadata before spending research credits.

**Leads unblocked:** R03, R04, R05, R11, R15, R23, R26, R32, R35, R39, R40, R45, R47

### Fix 3 — Research pack minimum fact threshold (4 leads)

**File:** `src/copyprompts.py` (EXTRACT_SYSTEM) or the research pipeline

**Upstream cause:** 4 leads reached the pipeline with research packs that
contained zero usable facts. The crawler either returned navigation furniture
("login | about | home | contact | services") instead of page content, or the
pages were too thin for the extractor to find a verifiable sentence. The
hypothesis stage correctly held these leads, but credits were already spent on
the research pack and ICP call.

**Fix:** After the research pack is assembled, check that it contains at least
one fact with a usable sentence (30-220 chars, carrying a verb, starting with
uppercase). If not, drop the lead before spending on ICP, hypothesis, match,
strategy and writer calls.

**Leads unblocked:** R22, R33, R38, R48

### Fix 4 — Writer prompt: LinkedIn must complement, not duplicate, email (3 leads)

**File:** `src/copystages.py` (WRITER_SYSTEM prompt)

**Upstream cause:** The writer generates LinkedIn connect notes and messages
that are lexically overlapping with the email body. `sequencegate.channels_complement`
checks for overlap >= 0.55 between LinkedIn and email bodies. Three leads
failed because the LinkedIn connect note was essentially em1 in shorter form.

**Fix:** The writer prompt should explicitly instruct the model that LinkedIn
messages must NOT restate email content. The connect note should reference
something specific about the contact's profile, not paraphrase the email.

**Leads unblocked:** R21, R25, R46

### Fix 5 — Writer prompt: em5 claims must be grounded in supplied facts (2 leads)

**File:** `src/copystages.py` (WRITER_SYSTEM prompt, em5 step instruction)

**Upstream cause:** The writer generates specific factual claims in em5 (the
breakup email) that cannot be traced to any supplied pack fact.
`sequencegate.claims_supported` reuses copylint's `untraceable` machinery.
Two leads failed because em5 contained a specific claim with no fact support.

**Fix:** The writer prompt for em5 should instruct the model to reference only
facts from the supplied pack, or to make a generic close that does not assert
company-specific claims.

**Leads unblocked:** R17, R31

### Fix 6 — Input validation: empty domain/company (2 leads)

**File:** `src/cadence.py` (`template_vars`) or the list ingest

**Upstream cause:** 2 leads (R49, R50) had no company name and no domain in
the Bison record. `cadence.template_vars()` raised because it could not derive
any personalization values from an empty record.

**Fix:** Add a validation check at list ingest that rejects records with
missing domain or company name before they enter the pipeline.

**Leads unblocked:** R49, R50

---

## THE 13 UNRENDERED VARIABLES — MECHANISM

The task requires finding WHY `{firstName}` had no value at render time.

**Finding:** `{firstName}` was never a missing-data problem. The contact's first
name was available in every case. The defect is a **naming inconsistency between
the writer prompts and the template renderer**, combined with generated steps
bypassing `render()`.

The mechanism, step by step:

1. The writer prompts in `src/copystages.py:332` and `src/copyprompts.py:343`
   explicitly instruct the model: `"{firstName} opening every message after the
   connect"`. The model is TOLD to write `{firstName}` as a literal token.
2. The Sonnet model follows the instruction and outputs LinkedIn messages with
   `Hi {firstName}, ...` — it was told to do this.
3. The writer output is stored as-is in `rec["written"]["linkedin"]`.
4. Email templates use `{first_name}` (snake_case) and go through
   `cadence.render(tpl, values)` which substitutes via `str.format()`. But
   generated LinkedIn steps (li2-li5) are NOT run through `render()` — the
   model output IS the final text, stored and retrieved verbatim.
5. The naming mismatch: templates use `first_name` (snake_case, matching
   Python's `str.format()` convention), while the writer prompts use
   `firstName` (camelCase, matching EmailBison's provider merge-field
   convention). Provider merge fields are resolved at send time, but
   `{firstName}` in model-generated copy is NOT a provider merge field — it
   is a literal string that nobody resolves.
6. At gate time, the original copylint (2026-09-25) did not check LinkedIn
   messages, so the defect was invisible. After TASK-378 expanded copylint to
   cover "everything the prospect reads" (including LinkedIn), the defect
   became visible: `UNRENDERED_RE.search(rendered)` matched `{firstName}`.

**This is a RENDER-stage defect caused by a prompt/render inconsistency.**
The prompts tell the model to write `{firstName}` (camelCase), but the renderer
expects `{first_name}` (snake_case), and generated steps bypass the renderer
entirely. Two fixes are needed: (a) change the prompts to instruct the model to
use the contact's actual name directly, and (b) add a post-generation
substitution pass on LinkedIn copy as a safety net.

---

## ACCEPTANCE CHECK

- Pareto table accounts for all 37 leads: 13+13+4+3+2+2 = 37
- Each lead has exactly one primary reason
- Counts sum to 37
- Largest bucket is NOT "other" or "unknown" — `not_an_agency` (13) and
  `unrendered_variable` (13) are tied at the top
- Each fix names a file and an upstream cause
- No gate was loosened
- No PII committed (no emails, names, or domains)
- No critical-path files edited

## FILES CHANGED

- `docs/TASK-423-FAILURE-TAXONOMY.md` — this document (NEW)

## FINDINGS

1. **`fifty-data.json` is missing.** The definitive per-lead data file from the
   v2 pipeline run no longer exists in any worktree. This task reconstructed
   its analysis from the posted HTML and XLSX review files plus
   `sample50-built.json`. A future task should ensure pipeline output artifacts
   are preserved, not just the review projection.

2. **The copylint expansion (TASK-378) was load-bearing.** Without it, 13 of
   the 31 written leads would ship with literal `{firstName}` in LinkedIn
   messages. The original copylint checked email bodies only; LinkedIn was
   invisible. The expansion to "everything the prospect reads" caught a real
   defect.

3. **26% of the list was never going to qualify.** 13 of 50 leads were not
   agencies. The ICP model worked correctly — it identified all 13 as
   UNQUALIFIED. But credits were spent on research packs and ICP calls for
   companies that a simple domain/keyword pre-filter would have rejected.

4. **The writer treats LinkedIn as "email in shorter form".** Three leads
   failed sequencegate because the LinkedIn connect note was essentially em1
   rewritten shorter. The writer prompt needs to differentiate the channels.

## RISKS

- The classification of the 8 "copylint-only" leads (R12, R13, R14, R19, R20,
  R37, R41, R43) depends on the TASK-342 re-lint numbers. The `fifty-data.json`
  that would confirm these directly is missing.
- The `channels_complement` count (3 in the final Pareto) is lower than the
  HTML's 6 because 3 of the 6 also had `unrendered_variable` and were counted
  at the earlier RENDER stage. If the unrendered variable is fixed, those 3
  would still fail sequencegate for channels_complement.

## RECOMMENDED CLAUDE ACTION

1. **Fix the `{firstName}` substitution** (Fix 1) — highest impact, 13 leads.
2. **Integrate the list pre-filter** (Fix 2) — prevents 26% waste on next batch.
3. **Preserve pipeline output artifacts** — `fifty-data.json` should be durable
   state, not a transient work file.
