PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-421 — Suppression List Audit (standing backlog refill, 2026-09-27)

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

## AUDIT RESULT

### 1. Every store of a suppression fact

There are **six independent stores**. They are NOT one canonical list.
They CAN disagree, and the system compensates by having two gate functions
(`eligibility.must_not_contact` and `channels.email_verdict`) consult all
of them in a defined priority order.

| # | Store | Location | Kind | Set by | Read by |
|---|---|---|---|---|---|
| 1 | **Domain suppression list** | `config/suppress.txt` (tracked template) + `config/suppress-local.txt` (gitignored, real roster) | Domain set, loaded by `ingest.load_suppress()` | Manual file edit | `channels._suppressed()` :127, `eligibility._suppressed()` :280, `discovery.py` :205, `validate.py` :183, `web/api.py` (14 call sites), `web/upload.py` :289, `refresh.py` :182/:326/:367, `plan.py` :222, `simulator.py` :212 |
| 2 | **Account-level suppression** | `rec["suppression"]` dict on each queue record | Record field, `{"unsubscribed": True, "since", "reason", "scope", "by"}` | `accountpolicy._suppress_account()` :549 | `channels._unsubscribed()` :93, `eligibility._paused()` :346, `accountsaturation._account_suppressed()` :102, `cadence.py` :1125 |
| 3 | **Contact-level suppression** | `contact["unsubscribed"]` (bool) + `contact["suppressed"]` (dict) on each contact | Contact fields | `accountpolicy._suppress_contact()` :479 | `channels._unsubscribed()` :92, `eligibility._replied()` :399, `account.py` :370, `accountsaturation._any_unsubscribed()` :97 |
| 4 | **Agency-wide DNC** | `agency-dnc.jsonl` beside the queue (hashed identifiers, append-only) | Separate file, SHA-256 fingerprints | `agencydnc.add()` :131 (no caller in `src/` — documented gap, PRODUCT-GAPS.md :1084) | `eligibility._suppressed()` :291 via `agencydnc.lookup()`, `hygiene.check` via `agencydnc.Index` |
| 5 | **Bounce state** | Derived from `EMAIL_BOUNCED` events in `rec["events"]` | Not stored — re-derived from event log on every read | `adapters.py` :131 (records the event) | `channels._bounced()` :96, `eligibility._email_checks()` :695, `account.bounces()` :183, `cadencesafety.py` |
| 6 | **Record drop for suppression** | `rec["drop_reason"]` starting with `"suppress"` | Record field | `ingest.py` :191 (at import time) | `channels._suppressed()` :133, `eligibility._suppressed()` :297, `eligibility._record_state()` :337 |

**Honest answer: several exist, and they CAN disagree.** The system does not
have one canonical suppression list. It has six stores consulted by two gate
functions that merge them. The priority order inside `eligibility.must_not_contact()`
(:358) is: domain suppress → client domain → record state → replied/stopped →
paused. The priority inside `channels.email_verdict()` (:136) is: unsubscribed
→ domain suppressed → no address → bounced → MX → verification.

### 2. Every prospect-facing write path checks suppression BEFORE writing

| Write path | Suppression check | File:line | How |
|---|---|---|---|
| **Email send (facing=True)** | `executionguard.revalidate()` | `providerwrites.py:2253` → `executionguard.py:985` | Re-reads record from DISK, calls `eligibility.decide()` which calls `must_not_contact()`. Runs immediately before the transport. |
| **Email send authorization** | `eligibility.decide()` | `executionguard.py:565` → `eligibility.py:645` | Gate 4 of `authorize()`. Calls `must_not_contact()` as first check. |
| **LinkedIn send** | `eligibility.must_not_contact()` | `heyreachfactory.py:1225` | Pre-transport loop over every contact, refuses if any reason fires. |
| **Email resume** | `_resume_revalidates_suppression()` | `providerwrites.py:1415-1473` | Reads every contact on every record the campaign names, calls `eligibility.must_not_contact()`. Added by TASK-331 specifically because resume has `facing=False` and would skip `revalidate()`. |
| **Push to provider (staging)** | `eligibility.decide()` | `push.py:153` | Full eligibility check before staging. |
| **Killswitch evaluation** | `eligibility.decide()` | `killswitch.py:218` | Full eligibility check. |
| **Funnel (batch evaluation)** | `eligibility.decide()` | `funnel.py:242` | Full eligibility check per lead. |
| **Web API send preview** | `eligibility.decide()` | `web/api.py:1408`, `web/api.py:2113` | Full eligibility check before showing result. |

**All facing writes go through `executionguard.revalidate()` which re-reads
from disk.** Non-facing writes (staging, resume) have their own suppression
checks. The gap TASK-331 measured — resume skipping revalidation — is closed
by `CONDITIONAL[EMAIL_RESUME]` at `providerwrites.py:1473`.

### 3. The 76 re-verification

**I cannot perform a fresh read from this worktree.** `work/queue.jsonl` is
not present here (confirmed: `ls work/queue.jsonl` → NOT PRESENT). Per
QWEN.md, live queue state lives in Claude's worktree only. The
`QUEUE-MANIFEST.json` is from 2026-09-20T12:32Z, before the 09-23 incident.

**What the documents say (memory, not fresh reads):**
- `PRODUCTION-HANDOFF-2026-09-26-MORNING.md:55`: "All 76 recipients are
  suppressed (`unsubscribed=True`, verified through `channels.email_verdict`,
  not just written) and stopped at the provider"
- `PRODUCTION-HANDOFF-2026-09-26-EVENING.md:70`: "76 recipients remain
  suppressed from the 09-23 blank-email incident, verified"
- `MONDAY-LAUNCH-PACKAGE-2026-09-28.md:143`: "Suppression and DNC, including
  the 76 recipients suppressed after the 09-23 incident"
- `providerwrites.py:1419`: "76 recipients are suppressed from the
  2026-09-23 blank-email incident" (comment in the resume guard)

**What is needed for a fresh read:** Claude (or a worker with access to
`work/queue.jsonl`) must iterate every record, find the 76 leads from
campaigns 491/492/494/495/497 that received blank emails, and confirm each
has `contact["unsubscribed"] == True` or `rec["suppression"]["unsubscribed"]
== True`. The lead IDs are in `work/blank-body-leads-2026-09-23.json`
(gitignored). The check is: for each lead's record_id and contact_key,
`eligibility.must_not_contact(rec, contact)` must return at least one
non-None reason.

**The mechanism that KEEPS them suppressed is verified by code review:**
- `_suppress_contact()` at `accountpolicy.py:479` sets `contact["unsubscribed"] = True`
- `eligibility._replied()` at `eligibility.py:399` reads `contact.get("unsubscribed")`
- `channels._unsubscribed()` at `channels.py:90` reads both `contact.get("unsubscribed")` and `rec["suppression"]["unsubscribed"]`
- Both `email_verdict()` and `must_not_contact()` call these on every evaluation
- There is no code path that clears `unsubscribed` without an explicit operator action

So the suppression is structurally durable — it persists on the record until
somebody explicitly clears it — but I cannot confirm the 76 specific records
still carry it without reading the live queue.

---

## RESULT BLOCK

STATUS: DONE (with one acceptance item owed — see below)
COMMIT SHA: 2070ce01
TESTS: Read-only audit, no code changes. Code paths verified by reading source.
FILES CHANGED: docs/qwen-tasks/RUNNING/TASK-421-suppression-list-audit.md (this file)
ARTIFACT KIND: Finding (audit report)

FINDINGS:
1. **Several suppression stores exist, not one canonical list.** Six independent
   stores (domain file, account suppression, contact suppression, agency DNC,
   bounce events, drop reason). Two gate functions (`eligibility.must_not_contact`
   and `channels.email_verdict`) merge them in priority order. They CAN disagree
   in principle, but the gates consult all of them so a suppression in any one
   store blocks the contact.

2. **Every prospect-facing write path checks suppression before writing.**
   All facing writes go through `executionguard.revalidate()` which re-reads
   from disk and calls `eligibility.decide()`. The resume gap (TASK-331) is
   closed by `_resume_revalidates_suppression()` at `providerwrites.py:1415`.
   LinkedIn writes check via `eligibility.must_not_contact()` at
   `heyreachfactory.py:1225`.

3. **The 76 re-verification is OWED.** This worktree has no `work/queue.jsonl`.
   A fresh read must be done from Claude's worktree. The mechanism is structurally
   durable (unsubscribed persists until explicitly cleared), but the 76 specific
   records need a live read to confirm.

RISKS:
- The agency DNC list (`agencydnc.add`) has no caller in `src/` — documented
  at PRODUCT-GAPS.md:1084. The list exists and is checked, but nobody writes
  to it through code. Additions are manual file edits.
- `config/suppress-local.txt` is gitignored and only in Claude's worktree.
  This worktree has only the template `config/suppress.txt`.

RECOMMENDED CLAUDE ACTION:
1. Run a fresh read of the 76 from `work/queue.jsonl` in Claude's worktree:
   for each lead from the incident (campaigns 491/492/494/495/497), confirm
   `eligibility.must_not_contact()` returns a non-None reason.
2. Consider whether the six-store architecture should be documented as a
   deliberate design choice (it is — each store answers a different question)
   or consolidated. The current state is correct but complex.
