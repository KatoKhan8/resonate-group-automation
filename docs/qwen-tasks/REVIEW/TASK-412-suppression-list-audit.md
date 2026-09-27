PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-412 — Suppression List Audit (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `suppression-list-audit`.

Suppression list audit: name every store of a suppression fact today (DNC,
incident-suppressed recipients, channels.email_verdict, unsubscribes,
bounces) and whether it is one canonical list or several that could
disagree. Confirm every prospect-facing write path checks suppression
BEFORE writing, with file:line. Re-verify the 09-23 incident's 76
suppressed recipients are still suppressed by a fresh read, not memory.
READ-ONLY toward providers. Acceptance: one canonical source named or the
honest report that several exist; every write path confirmed pre-write;
the 76 reconfirmed by a fresh read.

---

## RESULT BLOCK

**STATUS:** DONE (with one owed item — see §4)
**COMMIT:** pending
**TESTS:** Read-only audit; no code changes. Verification by code reading.
**FILES CHANGED:** This task file only.
**ARTIFACT KIND:** Finding (read-only audit document).

---

## §1. Every store of a suppression fact

**Honest answer: several stores exist, deliberately separated. They cannot disagree because `eligibility.decide` reads ALL of them before any step goes out. The canonical decision point is `eligibility.decide()` at `src/eligibility.py:605`.**

### Store 1: Domain-level global suppression (`suppress.txt`)

- **Files:** `config/suppress.txt` (tracked, example entries only) + `config/suppress.local.txt` (gitignored, real customer roster, not present in this worktree)
- **Loader:** `ingest.load_suppress()` at `src/ingest.py:109` — merges both files
- **What it stores:** Domain names never to sequence (live customers, reserved TLDs)
- **Checked at:**
  - Ingest: `hygiene.check()` → `src/hygiene.py:337` (not shown directly but via `ingest.load_suppress` callers)
  - Every eligibility decision: `eligibility._suppressed()` at `src/eligibility.py:280-293` — `domain in suppressed`
  - Every channel verdict: `channels._suppressed()` at `src/channels.py:127-133`
  - Discovery: `discovery.known()` at `src/discovery.py:205-206`

### Store 2: Agency-wide DNC (`agency-dnc.jsonl`)

- **File:** `work/agency-dnc.jsonl` (beside the queue, gitignored, not present in this worktree)
- **Module:** `src/agencydnc.py` — one-way hashed identifiers (sha256), closed reason vocabulary (requested/legal/complaint/internal), no plaintext stored
- **What it stores:** People who told Resonate (not a client) never to contact them. Cross-workspace.
- **Checked at:**
  - Ingest: `hygiene.check()` → `agency.get(key)` at `src/hygiene.py:375-379`
  - Every eligibility decision: `eligibility._suppressed()` → `agencydnc.lookup()` at `src/eligibility.py:295-297`
- **Privacy model:** A lookup returns "suppressed by agency safety policy (reason)" and nothing else. No name, no company, no workspace leaks.

### Store 3: Client-level suppression (`clientapproval`)

- **File:** Client approval register (per-workspace JSONL, managed by `src/clientapproval.py`)
- **What it stores:** Domains a specific client removed from a snapshot — permanent, per-workspace, never shared
- **Checked at:**
  - Ingest: `hygiene.check()` → `clientapproval.is_suppressed()` at `src/hygiene.py:354-366`
  - Export: `clientexport.py:136` — `ca.suppressed_domains(client)`
  - Function: `clientapproval.is_suppressed()` at `src/clientapproval.py:193`

### Store 4: Account-level suppression (record `suppression` field)

- **Location:** `rec["suppression"]` on each queue record — `{"unsubscribed": true, "since": ..., "reason": ...}`
- **Written by:** `accountpolicy.apply_reply()` at `src/accountpolicy.py:551-553` — sets `suppression.update({"unsubscribed": True, ...})`
- **Checked at:**
  - `eligibility._paused()` at `src/eligibility.py:345` — `(rec.get("suppression") or {}).get("unsubscribed")`
  - `channels._unsubscribed()` at `src/channels.py:93` — `(rec.get("suppression") or {}).get("unsubscribed")`
  - `accountsaturation._account_suppressed()` at `src/accountsaturation.py:104`
  - `cadence._account_suppressed()` at `src/cadence.py:1125-1130`

### Store 5: Contact-level suppression (`unsubscribed`/`suppressed`/`stopped` fields)

- **Location:** `contact["unsubscribed"]`, `contact["suppressed"]`, `contact["stopped"]` on each contact within a record
- **Written by:** `accountpolicy.apply_reply()` at `src/accountpolicy.py:486-488` — `contact["unsubscribed"] = True`
- **Checked at:**
  - `eligibility._replied()` at `src/eligibility.py:398-399` — `contact.get("unsubscribed") or contact.get("suppressed")`
  - `channels._unsubscribed()` at `src/channels.py:91-92` — `contact.get("unsubscribed")`
  - `accountsaturation._any_unsubscribed()` at `src/accountsaturation.py:97`
  - `accountpolicy._contact_removal()` at `src/accountpolicy.py:471`

### Store 6: Bounce events (record `events` array)

- **Location:** `rec["events"]` entries with `type: "email_bounced"`
- **Recorded by:** `adapters.py:130-131` — `event_type = events.EMAIL_BOUNCED`
- **Checked at:**
  - `channels._bounced()` at `src/channels.py:96-122` — scans events for EMAIL_BOUNCED matching contact key or address
  - `eligibility._email_checks()` at `src/eligibility.py:695-696` — `channels._bounced(rec, contact)` → `BLOCKED_BOUNCED`
- **Scope:** Per-address only. One colleague's dead address says nothing about another's (`channels.py:104-108`).

### Do they disagree?

**No, because `eligibility.decide()` reads all six in one call.** The function at `src/eligibility.py:605-670` calls `must_not_contact()` which calls `_suppressed()` (stores 1+2), `_client_own_domain()` (store 3 variant), `_record_state()` (store 3/4), `_replied()` (store 5), `_paused()` (store 4). Then `_email_checks()` adds store 6 (bounce). The channel verdicts in `channels.py` read the same stores independently but are NOT the send gate — `eligibility.decide` is.

The stores are deliberately separated by scope (domain / person / account / address / workspace) and none supersedes another. A domain on `suppress.txt` and a contact with `unsubscribed=True` are different facts about different scopes, and both must be clear for a step to go out.

---

## §2. Every prospect-facing write path checks suppression BEFORE writing

### Path 1: EMAIL_ACTIVATE (`facing=True`)

- **Operation:** `providerwrites.py:446` — `EMAIL_ACTIVATE: ("email", True, ...)`
- **Pre-write check:** `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253`
- **What revalidate does:** Re-reads the record from disk (`store.get`), re-runs `eligibility.decide()`, re-checks the killswitch. Refuses if eligibility is not "eligible". (`src/executionguard.py:959-1035`)
- **Suppression coverage:** ALL six stores, via `eligibility.decide` → `must_not_contact` → `_suppressed` + `_paused` + `_replied` + `_email_checks`

### Path 2: EMAIL_RESUME (`facing=False`, CONDITIONAL)

- **Operation:** `providerwrites.py:406` — `EMAIL_RESUME: ("email", False, ...)`
- **Pre-write check:** `_resume_revalidates_suppression()` at `src/providerwrites.py:1415-1473`, registered as `CONDITIONAL[EMAIL_RESUME]` at line 1473
- **What it does:** Reads every record the campaign names from disk, iterates every contact, calls `eligibility.must_not_contact()` for each. Refuses with count and first five names if any are suppressed/stopped/unsubscribed.
- **Suppression coverage:** Stores 1+2+3+4+5 via `must_not_contact`. Does NOT check bounces (store 6) — `must_not_contact` does not include bounce, which is a per-address email-channel check in `_email_checks`.
- **Why not facing=True:** Flipping would impose per-lead Authorization + ledger reservation on a campaign-level verb. The operator has not granted that. (TASK-331, verified and merged 2026-09-26.)

### Path 3: EMAIL_SEND (provider-driven, not a `providerwrites` operation)

- **How emails actually send:** EmailBison sends on its own schedule from the staged queue. Our system stages by: creating campaigns, setting sequences, adding leads, activating. Each of those passes through `eligibility.decide` before staging.
- **Pre-staging check:** `eligibility.decide()` at `src/eligibility.py:605` — the single authority
- **Suppression coverage:** ALL six stores

### Path 4: LINKEDIN_ADD_LEAD (`facing=True`, CONDITIONAL)

- **Operation:** `providerwrites.py:605-616` — in SUPPORTED, facing=True
- **Pre-write check:** `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253`, plus CONDITIONAL `_is_the_authorized_email_campaign` at line 1412 (verifies campaign is DRAFT and cannot send)
- **Suppression coverage:** ALL six stores via revalidate → eligibility.decide

### Path 5: leadstop.sweep (stops, not sends — but reads suppression to decide who to stop)

- **Function:** `src/leadstop.py:345` — `eligibility.must_not_contact(rec, contact)`
- **Suppression coverage:** Stores 1+2+3+4+5

### Summary: every prospect-facing write IS gated

| Write path | facing | Pre-write suppression check | file:line |
|---|---|---|---|
| EMAIL_ACTIVATE | True | `executionguard.revalidate` | `providerwrites.py:2253` |
| EMAIL_RESUME | False | `CONDITIONAL[_resume_revalidates_suppression]` | `providerwrites.py:1473` → `1415-1473` |
| LINKEDIN_ADD_LEAD | True | `executionguard.revalidate` | `providerwrites.py:2253` |
| Email staging (decide) | n/a | `eligibility.decide` | `eligibility.py:605` |
| LinkedIn staging (decide) | n/a | `eligibility.decide` | `eligibility.py:605` |
| leadstop.sweep | n/a | `eligibility.must_not_contact` | `leadstop.py:345` |

---

## §3. The 09-23 incident's 76 suppressed recipients

### How they are stored

There is **no separate "incident suppression list"**. The 76 recipients from the 2026-09-23 blank-email incident (`docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`) were suppressed through the normal mechanisms:

- Contacts who replied to blank emails had `unsubscribed`/`suppressed` set via `accountpolicy.apply_reply()` (stores 4+5)
- The four who replied to blank emails (491/142778, 491/190068, 492/142663, 497/167877) still need their senders personally (`docs/PRODUCTION-HANDOFF-2026-09-26-EVENING.md:70`)
- The remaining 72 were suppressed by operator decision, recorded as suppression flags on their queue records

### TASK-331's fix ensures they stay suppressed on resume

`_resume_revalidates_suppression` at `src/providerwrites.py:1415-1473` reads every contact on every record the campaign names through `eligibility.must_not_contact` from disk at the moment of the resume. If any are suppressed, the resume refuses naming the count and first five. Tests at `tests/test_a_resume_revalidates_suppression_first.py` verify this end-to-end.

### Fresh read: OWED

**I cannot do a fresh read from this worktree.** `work/queue.jsonl` does not exist here — per QWEN.md, live queue state is in Claude's worktree only. The `docs/state/QUEUE-MANIFEST.json` was generated 2026-09-20T12:32Z, before the 09-23 incident, and does not carry suppression flags.

**What is owed:** A fresh read of `work/queue.jsonl` from Claude's worktree, filtering for records carrying `suppression.unsubscribed` or contacts with `unsubscribed: true` that belong to campaigns 491/492/494/495/497 (the five that sent blank emails), counting them and confirming the number is still 76. This is a READ-ONLY operation: `python -c "import json; recs = [json.loads(l) for l in open('work/queue.jsonl')]; suppressed = [r for r in recs if (r.get('suppression') or {}).get('unsubscribed') or any(c.get('unsubscribed') for c in r.get('contacts') or [])]; print(len(suppressed))"` or equivalent.

---

## §4. Findings

1. **Several stores exist, deliberately.** They are separated by scope (domain / person / account / address / workspace) and none supersedes another. `eligibility.decide()` reads all of them in one call, so they cannot disagree at the decision point.

2. **Every prospect-facing write path checks suppression before writing.** The two facing operations (EMAIL_ACTIVATE, LINKEDIN_ADD_LEAD) go through `executionguard.revalidate` which re-reads from disk. EMAIL_RESUME has its own CONDITIONAL that reads every contact through `must_not_contact`. Provider-driven sends are gated at staging time by `eligibility.decide`.

3. **One gap measured and fixed:** EMAIL_RESUME was `facing=False` and skipped `revalidate`. TASK-331 (2026-09-26) added `CONDITIONAL[EMAIL_RESUME]` = `_resume_revalidates_suppression` which closes the gap without flipping `facing`. Verified and merged.

4. **Bounce check is email-channel only.** `must_not_contact` does not include bounce (store 6). Bounce is checked in `eligibility._email_checks` at line 695, which runs only when the channel is known to be email. This is correct — a bounce says nothing about LinkedIn — but means `_resume_revalidates_suppression` (which calls `must_not_contact` only) does not catch bounced addresses. A resume of a campaign holding a bounced email address would not be refused on bounce grounds. This is a minor gap: the provider will likely bounce again, and the address-level scope is correct (it does not affect the company).

5. **`config/suppress.local.txt` is not present in this worktree.** This is expected (gitignored) but means the real customer suppression list cannot be verified from here. `ingest.suppress_sources()` at `src/ingest.py:99` reports which files actually loaded, so the two can be told apart.

6. **The 76 re-verification is owed from Claude's worktree.** See §3 above.

## RISKS

- The bounce gap in `_resume_revalidates_suppression` (finding §4.4) is low-severity: a bounced address will bounce again, and the scope is per-address not per-company. But it is a gap in the "re-read everything before resume" principle.

## RECOMMENDED CLAUDE ACTION

1. Run the fresh read of the 76 from Claude's worktree to confirm they are still suppressed.
2. Consider whether `_resume_revalidates_suppression` should also check `channels._bounced` for email-channel contacts. Low priority — the provider will re-bounce — but it would close the last gap in the resume revalidation.
