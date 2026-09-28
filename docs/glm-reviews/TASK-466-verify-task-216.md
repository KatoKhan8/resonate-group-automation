# TASK-466 — Independent Verification of TASK-216

## Review Metadata

| Field | Value |
|-------|-------|
| Target task | TASK-216 |
| Target branch | origin/qwen-worker-10-r9 |
| Branch HEAD SHA | d3b76e3e172b59d86fd9541f15f47fcbf049c857 |
| SHA verified by | `git rev-parse origin/qwen-worker-10-r9` → d3b76e3e (matches) |
| Review worktree | .qwen/worktrees/task466-review (detached at d3b76e3e) |
| Review date | 2026-09-28 |
| Reviewer | Qwen (TASK-466) |

---

## 1. Does the Artifact Exist on This Ref?

**YES.** `docs/HEYREACH-BIND-ROUTE-2026-09-16.md` exists at `d3b76e3e`.

- Added in commit `3766e2c2` ("TASK-216: the bind route is POST /campaign/UpdateSettings, answer is (b)")
- Corrected in commit `135a6655` ("TASK-216 correction: UpdateSettings is the bind route, previous completion missed it")
- Both commits are ancestors of `d3b76e3e`
- `git show d3b76e3e:docs/HEYREACH-BIND-ROUTE-2026-09-16.md` returns the 221-line document

The task file is at `docs/qwen-tasks/DONE/TASK-216-find-the-supported-list-to-campaign-bind.md` on the branch (moved from TODO).

**VERIFIED.**

---

## 2. Do the Claims Match the Code?

### Claim: "No route named UpdateSettings appears in WRITE_ROUTES"

**CORRECT.** `WRITE_ROUTES` at line 1455 of `src/providers/heyreach.py` contains:
- `/campaign/Pause`, `/list/CreateEmptyList`, `/campaign/Create`, `/campaign/UpdateSequence`, `/campaign/AddLinkedInAccountsToCampaign`, `/campaign/RemoveLinkedInAccountsFromCampaign`, `/campaign/StopLeadInCampaign`, `/campaign/AddLeadsToCampaignV2`, `/campaign/Resume`, `/campaign/StartCampaign`, `/list/AddLeadsToListV2`

`UpdateSettings` is mentioned in a comment at line 1407 ("documents Create/UpdateSettings/UpdateSequence/UpdateAccounts/UpdateSchedule") but is NOT on the allowlist. The artifact correctly identifies this gap.

### Claim: Route listings match the code

**CORRECT.** Verified:
- `READ_ROUTES` (line 173): `("/campaign/GetAll", "/inbox/GetConversationsV2")` — matches
- `READ_ROUTES_ALL` (line 199): extends READ_ROUTES with `/lead/GetLead`, `/li_account/GetAll`, `/campaign/GetLeadsFromCampaign`, `/stats/GetOverallStats`, `/list/GetAll`, `/list/GetLeadsFromList`, `/campaign/GetCampaignsForLead` — matches
- `READ_GET_ROUTES` (line 231): `("/campaign/GetCampaignSequence", "/campaign/GetById", "/list/GetById")` — matches
- `WRITE_ROUTES` (line 1455): matches (see above)

Line numbers in the artifact are approximate ("~192", "~240", "~1421") vs actual (199, 231, 1455). Content is accurate.

### Claim: "LINKEDIN_ADD_LEAD is SUPPORTED and CONDITIONAL"

**CORRECT.** `providerwrites.py`:
- Line 174: `LINKEDIN_ADD_LEAD` in `SUPPORTED` with `prospect_facing=True`
- Line 1002: `CONDITIONAL[LINKEDIN_ADD_LEAD] = _campaign_is_a_declared_staging_campaign`

### Claim: "LINKEDIN_CREATE_CAMPAIGN is sealed (not in SUPPORTED)"

**CORRECT.** `LINKEDIN_CREATE_CAMPAIGN` is defined (line 121) and has a CONDITIONAL predicate (line 1139) but is NOT in the `SUPPORTED` dict. The artifact correctly says it is sealed.

### Claim: "Binding does not activate the campaign"

**CORRECT.** The code comments in `heyreach.py` lines 1473-1515 explicitly document that `StartCampaign` is a separate verb from configuration changes, and `providerwrites.py` lines 196-214 state that `LINKEDIN_START_EMPTY_FOR_STAGING` "is NOT LINKEDIN_ACTIVATE AND MUST NEVER BECOME IT."

### Claim: "No src/ changes were made"

**CORRECT.** `git diff master...d3b76e3e --stat -- src/` shows modifications to 16 src/ files, but NONE of these are from TASK-216. They are from other tasks on the same branch. TASK-216's FILES FORBIDDEN section prohibited src/ changes, and the task respected this.

**VERIFIED.**

---

## 3. Factual Error Found

### Step 2 of "Shortest Safe Sequence" conflates two distinct verbs

The artifact states:

> **Step 2:** Start the Empty Campaign
> Verb in `providerwrites`: `LINKEDIN_ACTIVATE` (via `heyreach.start_empty_for_staging`)

This is **WRONG.** The code has TWO SEPARATE verbs:

| Verb | Value | Prospect-facing | Status |
|------|-------|-----------------|--------|
| `LINKEDIN_ACTIVATE` | `heyreach.activate` | True | Sealed/deliberately not supported |
| `LINKEDIN_START_EMPTY_FOR_STAGING` | `heyreach.start_empty_for_staging` | False | SUPPORTED |

The code at `providerwrites.py` line 210 explicitly warns: "IT IS NOT LINKEDIN_ACTIVATE AND MUST NEVER BECOME IT."

Step 2 should reference `LINKEDIN_START_EMPTY_FOR_STAGING`, not `LINKEDIN_ACTIVATE`. These are architecturally distinct: one starts a zero-lead campaign (safe, not prospect-facing), the other starts a campaign that holds people (activation, prospect-facing, sealed).

**Severity:** Documentation error in a "what you would do next" section that the task explicitly says not to perform. Does not affect the core finding. But it conflates the system's most important safety boundary — the one between "start empty" and "activate" — and a reader following the sequence table without reading the code would wire the wrong verb.

**DISPOSITION:** Finding D1 below.

---

## 4. Falsifiability Assessment

This is an investigation task with no code changes and no tests. The falsifiability question becomes: **could the document's central claim be wrong while reading as correct?**

The central claim is that `POST /campaign/UpdateSettings` exists as a HeyReach API endpoint. The document cites three sources:
1. HeyReach official blog (`heyreach.io/blog/campaign-api`)
2. HeyReach CLI (`github.com/bcharleson/heyreach-cli`)
3. In-codebase comment at `heyreach.py` line 1407

I verified #3 against the code. I cannot independently verify #1 and #2 without network access (and the task boundaries prohibit provider calls). The claim is plausible and internally consistent with the code's own awareness of the route, but it rests on external sources I cannot re-derive.

**The safety-critical claims are falsifiable from code alone:**
- "UpdateSettings is NOT on WRITE_ROUTES" → verified, CORRECT
- "Binding does not activate" → verified from code architecture, CORRECT
- "LINKEDIN_ADD_LEAD is CONDITIONAL" → verified, CORRECT

**NOT VERIFIED:** The external vendor documentation claims (endpoint schema, status restrictions, list-locking behavior). These are cited from external sources and cannot be confirmed from code alone.

---

## 5. Would Merging Delete Anything?

**NO.** `git diff master...d3b76e3e --diff-filter=D` shows exactly one "deletion":

- `docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md` — the task file moving from TODO to DONE. This is expected task lifecycle, not destructive deletion.

No source files, no configuration, no other task files would be deleted.

**VERIFIED.**

---

## 6. Scope Drift

**SEVERE.** The branch carries 205 files changed / 30,881 insertions / 477 deletions against master. TASK-216's specific contribution is exactly 2 files:

1. `docs/HEYREACH-BIND-ROUTE-2026-09-16.md` (new, 221 lines)
2. `docs/qwen-tasks/DONE/TASK-216-find-the-supported-list-to-campaign-bind.md` (moved from TODO, content updated)

Everything else on the branch — 16 modified src/ files, ~100 new test files, dozens of new docs, new scripts, config changes — belongs to other tasks. Cherry-picking TASK-216's work would require extracting exactly these 2 files.

---

## Findings

### D1 — Step 2 names the wrong verb (Documentation Error)

| Field | Value |
|-------|-------|
| Severity | Medium |
| File | docs/HEYREACH-BIND-ROUTE-2026-09-16.md, Section 5 Step 2 |
| Summary | The safe sequence table names `LINKEDIN_ACTIVATE` where the code has a separate, distinct verb `LINKEDIN_START_EMPTY_FOR_STAGING` |
| Evidence | `providerwrites.py` line 130 defines `LINKEDIN_START_EMPTY_FOR_STAGING = "heyreach.start_empty_for_staging"` as a separate verb from `LINKEDIN_ACTIVATE = "heyreach.activate"` (line 126). Line 210 explicitly warns they are not interchangeable. |
| Impact | A reader following the sequence table would wire the sealed activation verb instead of the supported zero-lead start. The code would refuse it (LINKEDIN_ACTIVATE is sealed), so this is a documentation error rather than a safety hole — but it conflates the system's most important safety boundary. |
| Recommended fix | Change Step 2's verb from `LINKEDIN_ACTIVATE` to `LINKEDIN_START_EMPTY_FOR_STAGING` |

### D2 — External source claims not independently verified

| Field | Value |
|-------|-------|
| Severity | Low |
| File | docs/HEYREACH-BIND-ROUTE-2026-09-16.md, Sections 2-3 |
| Summary | The endpoint schema, status restrictions, and list-locking behavior are cited from vendor documentation and CLI source that this review could not independently fetch |
| Evidence | The review is read-only and network-restricted. The in-code comment at heyreach.py:1407 confirms the route's existence but does not document its constraints. |
| Impact | Low — the safety-critical claims (route not on WRITE_ROUTES, bind ≠ activation) are verified from code. The unverified claims are about provider behavior that would surface on first use. |
| Recommended fix | None required. Note for future tasks: when the bind route is actually implemented, the status restrictions and list-locking should be verified against a live provider response, not trusted from the document alone. |

---

## Disposition

**MERGE** — with one documentation defect to fix.

TASK-216 is an investigation-only task. Its artifact exists, its core findings are verified against the code, it made no prohibited changes, and it correctly identified a gap in the previous completion. The one error (D1) is in a forward-looking section the task explicitly said not to execute, and the code's own guards would catch the wrong verb if anyone tried to follow the table literally.

The scope drift on the branch is severe (205 files) but TASK-216's own contribution is clean (2 files). Cherry-pick, not merge.

---

## Recommendation

**MERGE** the two TASK-216 files (cherry-pick from the branch):
1. `docs/HEYREACH-BIND-ROUTE-2026-09-16.md`
2. `docs/qwen-tasks/DONE/TASK-216-find-the-supported-list-to-campaign-bind.md`

**Fix D1 before or immediately after merge:** change Step 2's verb from `LINKEDIN_ACTIVATE` to `LINKEDIN_START_EMPTY_FOR_STAGING`.
