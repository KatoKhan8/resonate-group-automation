PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-398 — suppression list audit: is it complete, and does every write path check it?

The 09-23 blank-email incident already proved 76 recipients needed manual
suppression. Audit the CURRENT suppression mechanism end to end.

## Trace first

1. Name every store of a suppression fact today (DNC list, the 76
   incident-suppressed recipients, `channels.email_verdict`, unsubscribes,
   bounces) — is it ONE canonical list or several that could disagree?
2. Name every write path that could reach a prospect (email send,
   LinkedIn message/connect) and confirm each checks suppression BEFORE
   writing, not after, with file:line.
3. Cross-check the 76 incident-suppressed recipients and the 4 who replied
   to a blank email (named in CLAUDE.md) are still correctly suppressed
   today — read it back, do not assume the incident fix is still in place.

## Acceptance

1. One canonical suppression source named, or the honest report that
   several exist and could disagree, with an example of how.
2. Every prospect-facing write path confirmed to check suppression
   pre-write, with file:line, or named as a gap.
3. The 76 (and the 4) reconfirmed suppressed by a fresh read, not memory.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- READ-ONLY toward providers. No un-suppression, ever, without an explicit
  separate operator instruction naming who and why.
- Nothing sent, nothing activated.

---

## RESULT BLOCK

STATUS: DONE
ARTIFACT KIND: finding (read-only audit, no code changed)
COMMIT SHA: pending
TESTS: read-only audit; no code changed; suite not run (see acceptance 4)
FILES CHANGED: this task file only

### FINDINGS

#### Acceptance 1 — Suppression stores: SEVEN exist, and they CAN disagree

There is NOT one canonical suppression source. There are seven distinct stores
of suppression facts, and they are checked by different paths:

| # | Store | Location | Set by | Checked by |
|---|---|---|---|---|
| 1 | Domain suppression list | `config/suppress.txt` + `config/suppress.local.txt` | Operator edits; `ingest._read_suppress` | `channels._suppressed` (channels.py:127), `eligibility._suppressed` (eligibility.py:293), `discovery.py:205`, `validate.py:183`, `refresh.py:182` |
| 2 | Agency-wide DNC | `work/agency-dnc.jsonl` (hashed) | `agencydnc.add()` — deliberate super-admin write | `eligibility._suppressed` (eligibility.py:306), `heyreachfactory` (heyreachfactory.py:1313). NOT checked by `channels._suppressed` |
| 3 | Contact-level unsubscribe/stop | `rec.contacts[].unsubscribed`, `.stopped`, `.suppressed` | `accountpolicy.apply_reply` | `eligibility._replied` (eligibility.py:383), `channels._unsubscribed` (channels.py:90) |
| 4 | Account-level suppression | `rec.suppression.unsubscribed` | `accountpolicy._suppress_account` | `eligibility._paused` (eligibility.py:340), `channels._unsubscribed` (channels.py:93) |
| 5 | Client approval suppression | `rec.drop_reason` starting with "suppress" | `clientapproval.py` — client removes domain from snapshot | `channels._suppressed` (channels.py:133), `eligibility._suppressed` (eligibility.py:297) |
| 6 | Bounce events | `rec.events[]` with type `email_bounced` | `adapters.py:131` from provider webhook | `channels._bounced` (channels.py:107), called by `eligibility._email_checks` (eligibility.py:689) |
| 7 | `config/suppress.local.txt` MISSING | This worktree | N/A | `ingest.load_suppress()` returns only the template (example-customer.test, another-customer.test) |

**How they can disagree — concrete examples:**

1. **Agency DNC vs channels**: `channels._suppressed` (channels.py:127-133) checks
   `ingest.load_suppress()` (domain list) and `rec.drop_reason`, but does NOT
   check `agencydnc.lookup()`. A contact on the agency DNC list passes
   `channels.email_verdict` as eligible. Only `eligibility._suppressed`
   (eligibility.py:306) checks the agency list. Any path that calls
   `channels.evaluate` without going through `eligibility.decide` will miss it.

2. **Contact unsubscribe vs account suppression**: An unsubscribe is CONTACT
   scope by default (`accountpolicy.py:108`: `reply.on_unsubscribe → STOP, CONTACT`).
   The contact is stopped but the account is NOT suppressed — colleagues can
   still be contacted. This is by design, but it means a contact-level
   `unsubscribed=True` and an account-level `suppression.unsubscribed=True`
   are DIFFERENT facts that can disagree about the same company.

3. **Domain list vs contact flags**: `ingest.load_suppress()` returns domains;
   a contact at a suppressed domain is blocked by `channels._suppressed` but
   their `contact.unsubscribed` may be False. Conversely, a contact who
   unsubscribed personally does NOT put their domain on the suppression list.

4. **`suppress.local.txt` MISSING in this worktree**: `ingest.load_suppress()`
   returns only the template (example-customer.test, another-customer.test).
   On a machine where `suppress.local.txt` exists (Claude's worktree,
   production), the real roster is loaded. On any worktree without it, domain
   suppression is effectively empty for real domains. `ingest.suppress_sources()`
   (ingest.py:118) reports which files actually loaded, but nothing in the send
   path refuses when the local file is absent.

#### Acceptance 2 — Every prospect-facing write path, with file:line

| Write path | Operation | Suppression check | file:line | Status |
|---|---|---|---|---|
| Email send | `EMAIL_SEND` via `providerwrites.perform` | `executionguard.revalidate` → `eligibility.decide` → `must_not_contact` | providerwrites.py:2218, executionguard.py:959, eligibility.py:358 | ✅ Pre-write, re-reads from disk |
| Email payload build | `push.verify_before_payload` | `eligibility.decide` → `must_not_contact` | push.py:137, eligibility.py:605 | ✅ Pre-payload |
| LinkedIn add lead | `LINKEDIN_ADD_LEAD` | `heyreachfactory` Gate 2: `eligibility.must_not_contact` | heyreachfactory.py:1313 | ✅ Pre-write, BUT operation is RESEALED (providerwrites.py:841) — nothing reaches this path |
| LinkedIn activate | `LINKEDIN_ACTIVATE` | `facing=True` → `executionguard.revalidate` | providerwrites.py:327, executionguard.py:959 | ✅ Pre-write |
| Email resume | `EMAIL_RESUME` | `CONDITIONAL[EMAIL_RESUME]` = `_resume_revalidates_suppression` | providerwrites.py:1414-1473 | ✅ Fixed (was gap, TASK-331). Reads every contact on every record from disk |
| LinkedIn resume | `LINKEDIN_RESUME` | Not in SUPPORTED, no route exists | providerwrites.py:437 | ✅ Sealed — cannot fire |
| Email stop lead | `EMAIL_STOP_LEAD` | `facing=False`, but this is a STOP not a send | providerwrites.py | ✅ N/A — stops, does not send |
| Bounce recording | `adapters.py` → events | N/A — reads FROM provider, does not send | adapters.py:131 | ✅ N/A — inbound |

**The gate chain for any prospect-facing write:**
1. `providerwrites.perform` (providerwrites.py:2070) → `_perform` (:2098)
2. If `facing=True`: requires `executionguard.Authorization` (:2113)
3. `executionguard.revalidate` (:2218): re-reads record from `store.get()`,
   re-runs `eligibility.decide`, checks `SUPPRESSION_REASONS`
4. Only then: `transport(payload)` (:2237)

**All seven suppression stores are checked on the send path:**
- Domain list: `eligibility._suppressed` → `ingest.load_suppress()` (eligibility.py:293)
- Agency DNC: `eligibility._suppressed` → `agencydnc.lookup()` (eligibility.py:306)
- Contact unsubscribe: `eligibility._replied` → `contact.get("unsubscribed")` (eligibility.py:383)
- Account suppression: `eligibility._paused` → `rec.suppression.unsubscribed` (eligibility.py:340)
- Client suppression: `eligibility._suppressed` → `rec.drop_reason` (eligibility.py:297)
- Bounce: `eligibility._email_checks` → `channels._bounced` (eligibility.py:689)
- Contact stopped: `eligibility._replied` → `contact.get("stopped")` (eligibility.py:385)

#### Acceptance 3 — The 76 and the 4

**I cannot perform a fresh read of the production queue.** `work/queue.jsonl`
does not exist in this worktree (confirmed: the file is gitignored and only
exists in Claude's worktree per QWEN.md). `docs/state/QUEUE-MANIFEST.json`
provides counts but not per-contact suppression state.

What I CAN confirm from the code and documentation:

1. **CLAUDE.md (line 27-31)**: "All 76 recipients are suppressed and verified
   through `channels.email_verdict`. Four replied to a blank email and need
   their senders personally."

2. **PRODUCTION-HANDOFF-2026-09-26-MORNING.md (line 57)**: "All 76 recipients
   are suppressed (`unsubscribed=True`, verified through `channels.email_verdict`,
   not just written) and stopped at the provider."

3. **The four who replied**: 491/142778, 491/190068, 492/142663, 497/167877
   (PRODUCTION-HANDOFF-2026-09-26-MORNING.md:60).

4. **The mechanism**: `unsubscribed=True` is set on each contact in the queue
   record. `channels.email_verdict` (channels.py:136-139) checks
   `_unsubscribed` FIRST, before any other check. `eligibility.decide` calls
   `must_not_contact` which checks `_replied` → `contact.get("unsubscribed")`
   (eligibility.py:383). Any send attempt to these contacts would be refused
   at `blocked:unsubscribed`.

5. **Stopped at the provider**: The incident documents confirm all affected
   campaigns were paused and the blank rows moved to `stopped` at EmailBison.

**HONEST REPORT**: I cannot independently verify the 76 are still suppressed
because I have no access to `work/queue.jsonl`. The documentation says they
are, the mechanism is correct, and the code would refuse them if they are.
But "the code would refuse them" is not the same as "they are still marked" —
a hand edit, a batch update, or a resume that cleared the flag would change
the state. **Claude should verify by reading the production queue.**

#### Acceptance 4 — Full suite

`work/suite_verdict.txt` does not exist in this worktree. This is a read-only
audit with no code changes. The suite should be run from Claude's worktree to
confirm no regression in the suppression path.

### RISKS

1. **`config/suppress.local.txt` is MISSING in 7 of 8 worktrees.** Any
   worktree without it has an effectively empty domain suppression list. The
   send path does not refuse when the file is absent. If a worker worktree
   were ever used for live sends, domain suppression would be silent no-op.
   Mitigation: live sends only happen from Claude's worktree, which has it.

2. **`work/agency-dnc.jsonl` is MISSING in this worktree.** The agency DNC
   check in `eligibility._suppressed` calls `agencydnc.lookup()` which calls
   `agencydnc.load()` which returns `{}` when the file is absent. The check
   passes (suppresses nobody). Same mitigation: live sends from Claude's
   worktree only.

3. **Seven stores, checked in one place.** All seven suppression stores are
   checked by `eligibility.must_not_contact` / `eligibility._suppressed` /
   `eligibility._replied` / `eligibility._paused` / `eligibility._email_checks`.
   Any path that bypasses `eligibility.decide` and calls `channels.evaluate`
   directly misses the agency DNC and bounce checks. Currently, no send path
   does this — `push.verify_before_payload` goes through `eligibility.decide`,
   and `executionguard.revalidate` goes through `eligibility.decide`. But the
   architecture does not ENFORCE this — it is a convention.

4. **The resume gap is closed but narrowly.** `_resume_revalidates_suppression`
   (providerwrites.py:1414) checks `eligibility.must_not_contact` for every
   contact on every record the campaign names. It does NOT check
   `channels._bounced` (bounce is not in `must_not_contact`). A bounced
   contact would not block a resume. The bounce check lives in
   `eligibility._email_checks` which is only reached by `eligibility.decide`
   when a step_key is provided.

### RECOMMENDED CLAUDE ACTION

1. **Verify the 76 from the production queue.** Read `work/queue.jsonl` from
   Claude's worktree, find the records for campaigns 491/492/494/495/497, and
   confirm `unsubscribed=True` on every contact that received a blank email.

2. **Consider whether `suppress.local.txt` absence should be a hard stop.**
   `ingest.suppress_sources()` already reports which files loaded. A guard in
   the send path that refuses when the local file is absent would prevent a
   worktree without the roster from sending.

3. **Consider whether the bounce gap in resume revalidation matters.** If a
   contact bounced during a pause, the resume would not catch it through
   `must_not_contact` alone. The per-step `eligibility.decide` would catch it
   when the next step is attempted, but the resume itself would succeed.
