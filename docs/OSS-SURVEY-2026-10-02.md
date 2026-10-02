# OSS survey — 2026-10-02

Standing weekly survey, set up 2026-09-23. Hard time box: one hour. Three
candidates, not eight — this run cut the candidate count rather than the
grounding, per the standing instruction. All claims below were checked
against the actual code on this branch (`master` as of this commit), not
assumed from the candidates' marketing pages or from the 2026-09-23 survey's
findings, which are a week and ~40 merges stale and were re-verified rather
than re-quoted.

`work/` is gitignored and unavailable to this session (cloud clone, no live
data). Nothing below needed it — all three candidates compare against code
and docs, not live counts — but anywhere a number would need `work/` it is
marked `UNVERIFIED (needs work/):` rather than guessed.

## Premises checked, and what survived

| # | Premise going in | What the code actually says, checked 2026-10-02 |
|---|---|---|
| 1 | "the killswitch can't stop a running campaign — is this still true?" | **Still true.** `src/killswitch.py` exports only state-check functions (`global_state`, `workspace_state`, `campaign_state`, `account_state`, `contact_state`, `step_state`, `state`, `require`) — no stop, cancel, or sweep. |
| 2 | "`leadstop.sweep()` already covers this, so there's nothing to adopt" | **False — checked and it doesn't.** `sweep()` → `_must_stop()` (`src/leadstop.py:338-348`) only fires on `eligibility.must_not_contact()` reasons in `executionguard.SUPPRESSION_REASONS` — per-person DNC/bounce/unsubscribe/reply. It never reads `killswitch.workspace_state()`. A workspace-wide `sending.live` flip does not make `sweep()` touch that workspace's rows. |
| 3 | "TASK-273 (adapter conformance suite) makes a shared-interface task redundant" | **Partially — TASK-273 is still TODO and is a different shape.** It tests the two existing adapters as-is, treating signature mismatches as named expected-differences. It does not propose an abstract base/Protocol. The two are additive, not duplicates, and are sequenced accordingly below. |
| 4 | "the compliance gate (TASK-271) already handles List-Unsubscribe, so there's nothing left here" | **The gate exists and passes on a body link, which is not the same compliance question as RFC 8058 one-click unsubscribe.** Confirmed both halves below. |
| 5 | "EmailBison's sequence-step API has grown a headers field since 09-23" | **No.** `src/providers/bison.py:1598-1606` — the dict is still exactly `{id, order, email_subject, email_body, wait_in_days, active, variant, variant_from_step, thread_reply}`. No field through which to set a real mail header. |

---

## 1. Temporal — durable workflow engine

**What it is.** A workflow orchestration engine (server + SDKs) for long-running,
stateful processes that must survive crashes and be controllable mid-flight.

**License.** MIT (self-hosted server; Temporal Cloud is a separate paid
offering, not required to use the OSS engine).

**What it does better, concretely.** Temporal workflows accept **signals** —
externally injected events, such as an operator cancellation, that reach an
*already-running* workflow instance and can alter its course (pause, cancel,
compensate) without restarting it. That is precisely the capability this
repository is missing and has already paid for once: CLAUDE.md documents that
turning `sending.live` off "was never a pause, and an active campaign kept
sending through it exactly as documented," because `src/killswitch.py` is a
pre-send gate, not a channel into running work. I re-checked this on current
`master` (table above, row 1) and it still holds, and I checked the one
plausible existing fix (`leadstop.sweep()`, row 2) and confirmed it doesn't
cover this case either — it stops individuals for suppression reasons, never
for a workspace-level kill.

**What adopting it would actually mean here.** Not the dependency — pulling
in a workflow server to orchestrate campaign sends would be a rewrite of
`src/executionguard.py`, `src/cadence.py` and the provider adapters, is wildly
out of proportion to the gap, and the rule above is explicit: never add a
dependency, and if the value is only available as one, say so and let the
operator decide. Said plainly: **it is only available as a dependency, and
adopting the dependency itself is not proposed here.**

What *is* worth adopting is the idea, built natively with primitives that
already exist and are already proven: `leadstop.sweep()` already does
per-contact provider-side stopping correctly (proven 2026-09-13, one lead
moved `in_sequence → stopped` in ~2 seconds). Teaching it to also ask "is this
contact's *workspace* currently killswitched?" — the same question
`killswitch.workspace_state()` already answers — turns a flip of
`sending.live` into something that actually reaches rows already scheduled at
the provider, instead of only gating the next decision. → **TASK-936** below.

---

## 2. django-anymail — unified ESP backend interface

**What it is.** A Django library giving one consistent API over many
transactional email providers (SES, Mailgun, Postmark, SendGrid, Postal,
and others).

**License.** BSD (3-clause).

**What it does better, concretely, naming the file it beats.** Every ESP
backend in anymail implements the same four-method contract off a common base
(`build_message_payload`, `post_to_esp`, `parse_recipient_status`, and an
`esp_name` property), over a shared `BasePayload` carrying the fields every
message has regardless of provider. Adding a thirteenth ESP to anymail means
implementing four known methods against a known contract.

This repository has no equivalent. `src/providers/bison.py` (2,262 lines) and
`src/providers/heyreach.py` (3,135 lines) are independent modules with no
base class, ABC, or `typing.Protocol` between them — confirmed again today,
same as the 2026-09-23 finding. Where the verb names coincide, the
signatures still don't: `bison.set_sequence(campaign_id, title, steps)`
(`bison.py:1609`) vs. `heyreach.set_sequence(campaign_id, sequence)`
(`heyreach.py:2105`); `bison.resume_campaign(campaign_id, expect_leads=None,
attempts=8, interval=2.0)` (`bison.py:1876`) vs. `heyreach.resume_campaign
(campaign_id)` (`heyreach.py:1630`). TASK-273 (still TODO, unchanged since
09-23) already plans a conformance *suite* over these two as they stand,
explicitly treating the mismatches as named expected-differences rather than
failures — a reasonable, smaller goal that does not require a shared
interface to exist.

**What adopting it would actually mean here.** Not the dependency (this
system doesn't use Django, and anymail is Django-coupled besides). The
transferable idea is the **contract itself**: a `typing.Protocol` (stdlib,
zero dependency, zero runtime behavior change — it only exists for a type
checker and a reader) naming the handful of verbs that genuinely mean the
same thing on both adapters today, so a third sequencer adapter for the next
client has something to be checked against instead of a blank page. This is
explicitly scoped *after* TASK-273, because TASK-273's own asymmetry table is
what will show which verbs are candidates for a shared signature and which
are load-bearing differences (e.g., HeyReach's large sequence-validation
surface that Bison has none of in the adapter layer — `heyreach.py`'s
`validate_sequence_for_write`, `sequence_hazards`, `refuse_unsupported_sequence`
vs. nothing comparable in `bison.py`). → **TASK-937** below, sequenced after
TASK-273.

---

## 3. Postal — self-hosted mail delivery platform

**What it is.** A complete, self-hosted outbound/inbound mail server (SMTP
+ API), an alternative to running your own Postfix/Exim stack.

**License.** MIT.

**What it does better, concretely.** Postal's own maintainers are actively
tracking RFC 8058 one-click unsubscribe compliance — the `List-Unsubscribe`
**and** `List-Unsubscribe-Post` header pair that Gmail and Yahoo's 2024+
bulk-sender rules require for senders above their volume thresholds (a bare
`List-Unsubscribe` header, or a link in the email body, satisfies neither
rule). Postal exposes both as literal SMTP headers on send
(`"headers": {"list-unsubscribe-post": "..."}`) — a mail-protocol-level
affordance this estate's provider does not have at all.

I checked this against what TASK-271 actually built, not against what the
09-23 doc said was planned, because `COMPLIANCE.md` now exists and
`src/executionguard.py` now has an unsubscribe-compliance gate
(`:589-608`, `_has_unsubscribe_affordance` at `:1163`,
`_named_unsubscribe_setting` at `:1175`) — TASK-271 shipped its code even
though the task file itself is still sitting in `TODO/` rather than `DONE/`
(a queue-hygiene gap, noted here, not mine to fix). **What it actually
checks**: a link or merge-field token matching `unsubscribe|opt-out|manage
preferences|...` in the rendered email body (`_UNSUBSCRIBE_URL` regex,
`executionguard.py:1154-1159`), or a named provider-level setting. Both are
real affordances and the gate is correctly built against the rule it says it
enforces. **But neither one is a `List-Unsubscribe` header**, and the gate's
own comment block (`:1241`) already says so explicitly. Confirmed today
(premise 5, table above): `bison.py`'s sequence-step payload still has no
`headers` field, so there is no way to set a real header through this
provider even if we wanted to. Separately, `executionguard.py:1214-1219`
records that EmailBison's own native switch for this, `can_unsubscribe`,
reads back `False` on 22 of 22 campaigns.

**What adopting it would actually mean here.** Not the dependency — running
a mail server is a different product decision than the one this task is
scoped to make, and is not proposed. The adoptable piece is narrower:
`COMPLIANCE.md` should say, in its own words, that the unsubscribe-affordance
gate satisfies this repository's own compliance bar but does not satisfy
Gmail/Yahoo's one-click requirement, and that satisfying it is not reachable
from the current provider without a capability EmailBison does not expose.
That is a documentation correction, not a feature — "nothing cross-checked"
is exactly the failure mode `COMPLIANCE.md` exists to prevent, and right now
the document is silent on a real, named, external compliance bar it could be
read as having already met. → **TASK-938** below.

---

## What's queued

Three tasks, `docs/qwen-tasks/TODO/TASK-936.md` through `TASK-938.md`.
Numbered from 936 (highest existing task file, pre-survey, was TASK-935).
None of them add a dependency, none of them touch `src/providers/*`,
`src/clientapproval.py`, `config/`, or `work/*.jsonl`, and none of them copy
code from the surveyed projects — each describes the idea in this
repository's own words against this repository's own primitives.

**The operator decides what, if anything, enters the active queue.** Nothing
here is approved by virtue of being written down.
