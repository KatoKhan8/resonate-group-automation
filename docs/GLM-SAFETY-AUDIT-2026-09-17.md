# GLM safety audit - copy-approval guards

2026-09-17T08:41:16.956670+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Everything below is a lead to check against the code and the tests by hand. A model's opinion is evidence to investigate, never a reason to edit a safety gate.

---

## _certified_copy

`glm-5.3`, 56.565s, usage {'prompt_tokens': 882, 'completion_tokens': 3351, 'total_tokens': 4233, 'reasoning_tokens': 3041, 'cached_tokens': 832}.

**1. DEFEAT — the fingerprint proof is performed, then `extra` is merged on top of it.**

**2. Exact steps:**

1. Operator approves the step: `stamp["fingerprint"] = H(channel, subject, body, note)` over the approved words.
2. Caller invokes `_certified_copy(step, key, extra={...})` where `extra` contains a colliding key — `"subject"` or `"body"` (e.g., a variant branch passing the chosen variant's copy as `extra` rather than writing it back into `step`).
3. The check passes: `material` is a copy of `step` whose subject/body are re-set to `step`'s own values, so the hash covers only the approved words, and equality holds.
4. `entry.update(extra)` then overwrites `subject`/`body` **after** verification.
5. `_approved_copy`/`_ensure_leads` treat the return value as certified; the provider receives `extra`'s strings in `{SUBJECT_1}`/`{BODY_1}`.

**Prospect receives:** whatever strings `extra` carried — unapproved subject/body — while every layer reports success.

Everything else fails closed; `message`/`linkedin_action` being unhashed is irrelevant here since this function stages only subject/body. If audit of callers proves `extra` never carries copy keys, downgrade to NO DEFEAT FOUND — the hatch is otherwise unused.

## approve_step

`glm-5.3`, 47.101s, usage {'prompt_tokens': 989, 'completion_tokens': 2842, 'total_tokens': 3831, 'reasoning_tokens': 2519, 'cached_tokens': 320}.

**DEFEAT FOUND** (LinkedIn path).

Root cause: the sanitizing loop syncs exactly the fingerprinted fields (channel/subject/body/note) plus `template`. `message` and `linkedin_action` — the words a LinkedIn step actually sends — are in neither the fingerprint nor the loop. The comment itself defines the bug class ("a word the stamp does not cover sitting in the slot the sender reads") and then leaves two such words in the slot.

Steps:
1. Model drafts a LinkedIn step; slot `cadence[c][s] = {channel:"linkedin", message:"stale model text", linkedin_action:"connect"}`.
2. Operator reviews and calls `approve_step` with the corrected `step = {channel:"linkedin", message:"approved words", linkedin_action:"message", note:...}`.
3. `fingerprint(step)` hashes channel/subject/body/note — none carry the LinkedIn words. Loop copies only channel/subject/body/note/template; the slot's `message` and `linkedin_action` survive untouched.
4. At staging and again at activation, `_step_copy` certifies by recomputing the fingerprint over the same uncovered fields — it matches the stamp — and stages the slot's `message`.

Prospect receives: the stale, unapproved model text, while the stamp, `store.log`, and `DRAFT_APPROVED` all report the corrected step as approved and certified.

(Secondary: `template` is stored unfingerprinted and expanded at read time, so post-approval template edits also reach prospects.)

## _step_copy

`glm-5.3`, 20.173s, usage {'prompt_tokens': 961, 'completion_tokens': 1246, 'total_tokens': 2207, 'reasoning_tokens': 917, 'cached_tokens': 320}.

**DEFEAT FOUND — the InMail `message` field is outside the fingerprint.**

`approval.fingerprint(step)` hashes channel, subject, body, note. The inmail branch returns `step["message"]` — a field the fingerprint never covers.

**Steps:**
1. Operator creates an InMail step: `{"channel": "linkedin", "linkedin_action": "inmail", "subject": "Intro", "message": "approved body", "note": "", "body": ""}` and approves it. `fingerprint` covers channel+subject only — `message` is unhashed.
2. After approval, edit `message` to any unapproved text ("Get 50% off today only — link"). Touch nothing else.
3. At staging, `_step_copy` recomputes `_approval.fingerprint(step)` → identical (message not hashed), so the check passes. Channel is linkedin, action is inmail, subject and message non-empty → returns `{"subject": "Intro", "message": "…unapproved…"}`.
4. Copy is staged and activated; every check reports success.

**Prospect receives:** the approved subject over an InMail body no operator ever saw — edited after approval, under a stamp that still verifies.

**Second instance, same hole:** the fallback branch (`note or message`). A step approved with an empty `note` plus an injected `message` returns that unhashed text for message/open-profile steps. Also `linkedin_action` itself is unhashed, so flipping a connect step to inmail swaps copy fields without invalidating the stamp.

## _ledger_is_silent

`glm-5.3`, 43.146s, usage {'prompt_tokens': 933, 'completion_tokens': 2469, 'total_tokens': 3402, 'reasoning_tokens': 2153, 'cached_tokens': 320}.

**1. NO DEFEAT FOUND** (for `_ledger_is_silent`).

**2. N/A.**

Why the candidate defeats don't construct from the visible code:

- **Superseded rows:** the reservation-before-call row is superseded only by a settle row; a retry appends a fresh reservation *after* the settle, so "last row per key" still lands on a `MAY_HAVE_REACHED` state. Wrong-direction risk doesn't arise from the append-only design here.
- **Crash mid-send:** reservation is written before the provider call, so an in-flight send leaves an `attempted` row → reads non-silent. Safe direction.
- **Unreadable ledger / missing campaign_id:** returns False (not silent). Fail-closed.

Two residual risks I could not verify and therefore do not count as findings: (a) the membership of `LEDGER_MAY_HAVE_REACHED` — if a settle row recording a *confirmed* delivery uses a state name absent from that set, a sent campaign would read silent; (b) asymmetric normalization — this check strips its own `campaign_id` but compares rows with `str(row.get("campaign_id"))` unstripped, so ledger rows written with padded IDs would be invisible. Neither is constructible without the constant's contents or the writer's behavior. The decisive defeats hinted at (fingerprint ignoring `message`/`linkedin_action`; per-lead custom variables) live in `_certified_copy`/`_step_copy`, not here.

