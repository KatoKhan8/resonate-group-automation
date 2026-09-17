---
title: "EmailBison Cohort Truth — provider-grounded numbers for a clean replacement campaign"
date: "2026-09-16"
scope: "EmailBison workspace 10 (PRODUCTIVE), sender 2736, CONTROL cohort"
method: "READ-ONLY. No provider write of any kind was performed. No campaign was created, modified, archived or activated."
builds_on:
  - "docs/BISON-CONTROL-PAYLOAD-2026-09-16.md"
  - "docs/BISON-ARCHIVE-ROOT-CAUSE-2026-09-16.md"
  - "OPERATOR-AUTHORIZATION-2026-09-16.md"
---

# EmailBison Cohort Truth — 2026-09-16

**PII policy.** Every identifier is SHA-256 hashed (12 hex chars), per the
repository-wide guard in `tests/test_fixture_hygiene.py`. No email address,
person name, company name or domain appears in this document. Body text shows
`<name:HASH>` and `<company:HASH>` placeholders.

**Provenance.** Every number below was read from the provider or recomputed
from `work/queue.jsonl` (via `src.store`) during this session.
`work/queue.snapshot.jsonl` was NOT read: it is stamped
`2026-09-15T17:52:12+00:00 from master cf23154`, which predates the operator's
2026-09-16T11:37:38Z approval run, and reading it is what produced the wrong
cohort numbers previously.

**Credential binding, checked before every read.**
`bison.bound_workspace()` -> `{"id": 10, "name": "PRODUCTIVE"}`. Every
collision read was pinned with `expect_workspace=10`.

---

## HEADLINE

    EMAILBISON_READY_COHORT = 0        (measured today, against every gate)
    ceiling after remediation  = 10    (the declared cohort, if two defects are fixed)
    exposure if 10 x 3 were built = 30 emails, paced at 15/day (sender limit)

Two defects block a clean build. Neither is a per-contact exclusion; both are
system-level and both are silent.

| # | Defect | Effect |
|---|---|---|
| **D1** | The approval fingerprint covers text that is **not** the text the staging path would send. All 30 of 30 steps. | A replacement campaign would ship unapproved words under an operator approval granted for different words. |
| **D2** | All 10 leads read `stopped` at the provider in campaign 485, so `collision.account_policy` returns HOLD and `bisonfactory._refuse_colliding_leads` refuses all 10. | The factory will not stage the cohort at all. |

---

## 1. PROVIDER TRUTH — workspace 10

**Measurement.** `GET /api/campaigns?per_page=100` walked to completion through
`bison._paged` (23 of 23 rows, `meta.total` reconciled); per campaign
`bison.sequence_steps()` and `bison.campaign_senders()`. Lead counts, emails
sent and daily caps are the provider's own `total_leads`, `emails_sent` and
`max_emails_per_day` fields on the campaign row.

| id | status | leads | contacted | emails sent | replied | steps | cap/day | senders | name |
|---|---|---|---|---|---|---|---|---|---|
| 485 | **draft** | 10 | 0 | **0** | 0 | 3 | 20 | `[2736]` | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL [productive-email-control-v2] |
| 484 | **draft** | 0 | 0 | **0** | 0 | 5 | 20 | `[]` | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL [productive-email-control-v1] |
| 481 | **paused** | 23 | 0 | **0** | 0 | 5 | 20 | `[2736, 2737]` | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1 |
| 451 | **completed** | 1 | 1 | **1** | 0 | 1 | 1 | `[3948]` | RESONATE - PRODUCTIVE CANARY |
| 424 | draft | 0 | 0 | 0 | 0 | 0 | 1000 | `[]` | INTERESTED - Heyreach - Sep 3 |
| 423 | draft | 0 | 0 | 0 | 0 | 0 | 1000 | `[]` | MAYBE - Heyreach - Sep 3 |
| 418 | draft | 0 | 0 | 0 | 0 | 10 | 1000 | 2 inboxes | PRODUCTIVE - SOFTWARE DEVELOPMENT - NOT CONNECTED |
| 352 | **active** | 21,291 | 20,432 | **92,974** | 547 | 44 | 5000 | 15+ inboxes | HeyReach Connection Campaign |
| 335 | completed | 547 | 1,342 | **9,759** | 27 | 22 | 5000 | multi | legacy |
| 334 | completed | 326 | 1,080 | **7,269** | 33 | 22 | 1000 | multi | legacy |
| 331 | completed | 643 | 1,397 | **10,299** | 163 | 8 | 1000 | multi | legacy |
| 330 | completed | 103 | 736 | **4,028** | 95 | 8 | 1000 | multi | legacy |
| 329 | completed | 556 | 718 | **4,300** | 15 | 8 | 1000 | multi | legacy |
| 328 | **active** | 10,285 | 7,605 | **35,445** | 757 | 8 | 1000 | multi | legacy |
| 327 | **active** | 9,676 | 7,975 | **44,986** | 524 | 8 | 1000 | multi | legacy |
| 274 | archived | 9,734 | 4,994 | **28,331** | 73 | 35 | 1000 | `[]` | legacy |
| 266 | archived | 519 | 315 | **315** | 3 | 6 | 1000 | `[]` | legacy |
| 265 | archived | 993 | 1,609 | **1,609** | 4 | 6 | 1000 | `[]` | legacy |
| 264 | archived | 311 | 415 | **415** | 0 | 6 | 1000 | `[]` | legacy |
| 263 | archived | 297 | 299 | **299** | 0 | 6 | 1000 | `[]` | legacy |
| 262 | archived | 3 | 525 | **525** | 20 | 6 | 1000 | `[]` | legacy |
| 234 | archived | 0 | 0 | 0 | 0 | 17 | 1000 | `[]` | legacy |
| 200 | archived | 0 | 0 | 0 | 0 | 22 | 1000 | `[]` | legacy |

### Status of 451, 481, 484, 485 — confirmed

- **451 — `completed`.** 1 lead, **1 email sent**. `GET /campaigns/451/scheduled-emails` returns exactly one row: `status: sent`, `sent_at: 2026-09-14T16:24:20Z`. **This is the only Resonate-originated touch in the estate, and the belief that confirmed touches to date are exactly 1 on 451 is CONFIRMED.**
- **481 — `paused`, NOT draft.** This corrects a premise carried into this task. 23 leads, 0 emails sent, 5 steps, senders `[2736, 2737]`.
- **484 — `draft`.** 0 leads, 5 steps, **no sender attached**.
- **485 — `draft`.** 10 leads, 3 steps, sender `[2736]`, 0 scheduled emails.

### Anything that has SENT

Scoped to Resonate-built campaigns: **only 451, exactly 1 email.**

Scoped to the workspace as a whole this is not the picture, and the difference
matters for every collision and fatigue question below. The client's
pre-Resonate estate has sent **240,554 emails** across 14 campaigns, and
**three of them are `active` right now** — 352, 328 and 327, whose `updated_at`
timestamps are 2026-09-16T18:01, 17:53 and 02:01, i.e. today. A cold-outreach
claim about this workspace is a claim about Resonate's own campaigns, never
about the estate.

### FLAG — campaign 481 is a live hazard

`bison.membership(481)` reads 23 leads: **14 `stopped` and 9 `sending_paused`**.
`sending_paused` is in `bison.RESUMABLE_STATES` and the module documents why:
it is the campaign's state borrowed by the membership and it reverses the moment
somebody resumes. 481 holds a **5-step, fully non-threaded sequence** (all five
steps `thread_reply: false`, five independent subjects `{SUBJECT_1}`..`{SUBJECT_5}`).
**Nine of the ten CONTROL cohort contacts are those nine `sending_paused` leads.**
A single resume of 481 would send 9 x 5 = 45 emails that violate the threading
invariant to the exact people the CONTROL campaign is being built for.

### FLAG — campaign 484 is at risk of being archived again

`docs/BISON-ARCHIVE-ROOT-CAUSE-2026-09-16.md` establishes that this provider
archives a campaign with no sending account attached, within minutes. 484 is
`draft` with `senders: []` right now.

---

## 2. SENDER 2736

**Measurement.** `bison.sender_emails(expect_workspace=10)` — full walk, 225 of
225 rows reconciled against `meta.total` (15 pages x 15). `require_workspace(10)`
passed before the first page.

| field | value |
|---|---|
| id | **2736** |
| exists in workspace 10 | **YES** (present in the credential-bound inventory of 225) |
| address | `<email:2f2a9d9c0f30>` on the client's dedicated sending domain |
| status | **`Connected`** |
| type | `custom` (Gmail IMAP/SMTP: `imap.gmail.com:993`, `smtp.gmail.com:465`) |
| **daily_limit** | **15** |
| **warmup_enabled** | **true** |
| emails_sent_count (lifetime) | 1,742 |
| total_leads_contacted_count | 292 |
| unique_replied_count | 11 |
| bounced_count | 11 |
| last updated | 2026-09-16T17:26:21Z |

**Caveat on "verified".** The provider exposes no verification field on a
sender-email row. `status: "Connected"` is what it does state, and that is what
is reported here. There is no `workspace`, `team`, `tenant` or `owner` field on
any sender row either (see the probe matrix in `src/providers/bison.py`), so
2736's membership of workspace 10 is established by the credential binding —
`/api/users` reporting workspace 10 — and not by any field on the row.

**The binding cap is 15, not 20.** Campaign 485 carries `max_emails_per_day: 20`
but 2736's own `daily_limit` is 15. With one sender attached the effective pace
is **15 emails/day**.

---

## 3. THE READY COHORT

### Candidate pool

Recomputed from `work/queue.jsonl` (550 records, 277 contacts, all
`client: productive`). **51 contacts carry any `em*` cadence step**; those are
the candidates. 43 of the 51 hold `em1`+`em2`+`em3` in stored state.

### Gate results

Gates were run with `campaign = campaigns.require("productive-email-control-v2")`
throughout, and `eligibility.decide(..., step=expanded_step)` — the only
authority on whether a step may go out.

| gate | source of truth | in-cohort 10 | other 41 candidates |
|---|---|---|---|
| tenancy | credential -> ws 10; `rec.client == productive`; `eligibility._identity` | **10 PASS** | 41 PASS |
| verified email | `verification.resolve` + `lint.sendable` (re-derived, never read off the record) | **10 PASS** (`verified`, sendable) | 41 PASS |
| resolved persona | `contact.persona` | **10 PASS** (all `economic_buyer`) | 41 PASS (36 `economic_buyer`, 5 `champion`) — **no `persona=None` remains in the estate** |
| has an em2 step at all | stored cadence keys | **10 PASS** | 4 FAIL (`em1/em3/em5`, `em1/em4/em5` x2, `em1/em2/em4/em5` variants) |
| fatigue | `fatigue.account_check` | **10 PASS** (`ok`) | 41 PASS |
| must-not-contact (suppression, DNC, reply, pause, drop) | `eligibility.must_not_contact` | **10 PASS** | 41 PASS |
| approval fingerprint currency | `approval.is_approved(rec, ck, sk, expanded_step)` | **10 PASS** (30/30 steps current) | **41 FAIL** — 0 carry a current approval; 13-14 carry a stale stamp, the rest carry none |
| campaign selection | `eligibility._selected` | 10 PASS | **41 FAIL** `blocked:not_selected_for_campaign` |
| prior contact at the provider (address level) | `collision.check_address(expect_workspace=10)` | **10 PASS** — every one has `emails_sent: 0` | not measured (excluded earlier) |
| **account collision** | `collision.check_account` + `collision.account_policy` | **0 PASS / 10 FAIL** | not measured |
| campaign-level approval | `eligibility._campaign` | **10 HELD** `held:campaign_not_approved` | — |

### The account collision gate — why every one of the ten fails

`bisonfactory._refuse_colliding_leads(plan["leads"], 10)` was executed
read-only against the real plan. It raises:

    FactoryRefused: 10 contact(s) collided with the client's own estate:
    ... hold - a campaign at this account ended early (stopped) and the
    status does not say whether we stopped it, they unsubscribed, or the
    provider stopped it on a reply ...

The cause is our own campaign 485. `bison.membership(485)` reads **10 of 10
leads as `stopped`**. `stopped` is in `collision.SUSPECT_STATUSES`, so
`account_policy` returns HOLD for every account, and `_refuse_colliding_leads`
blocks HOLD as well as STOP. This is a self-inflicted hold created when 485 was
archived for having no sender attached and its memberships were stopped; it is
not evidence about the prospects.

**With the 481/485 membership rows excluded, the true account picture is:**

| # | record | account verdict | leads at domain | emails sent at domain | policy (ours stripped) |
|---|---|---|---|---|---|
| 1 | `ff930f49050f` | clear | 1 | 0 | allow — no prior contact |
| 2 | `d881cb9457f6` | clear | 1 | 0 | allow — no prior contact |
| 3 | `73636ff041b0` | clear | 1 | 0 | allow — no prior contact |
| 4 | `90dc872ce83e` | clear | 1 | 0 | allow — no prior contact |
| 5 | `a02d0a715cb8` | clear | 1 | 0 | allow — no prior contact |
| 6 | `b15936a38d71` | clear | 1 | 0 | allow — no prior contact |
| 7 | **`b580268f93f2`** | **touched** | **2** | **13** | allow — *history, not a live conflict* |
| 8 | `d00a60562edd` | clear | 1 | 0 | allow — no prior contact |
| 9 | `646934233472` | clear | 1 | 0 | allow — no prior contact |
| 10 | `73dff24eb5e8` | clear | 1 | 0 | allow — no prior contact |

**Record `b580268f93f2` is not a cold account.** A colleague at that domain
(lead 169009, created 2026-04-23) received **13 emails** — 8 in campaign 328 and
5 in campaign 352, both `sequence_finished`, zero replies, zero opens. Under
`collision.account_policy` this is ALLOW, but the policy's own wording requires
it be REPORTED so that "cold outreach" is never claimed about a worked account.

This also corrects the record on TASK-177: that check passed
`b580268f93f2` with "0 prior email(s)" because it asked
`check_address` — a **person-level** question — and never
`check_account`. The 13 emails went to a different person at the same company.
This is the exact failure `collision.account_policy`'s own docstring was written
about ("nine cold emails to a colleague on the same record... and every gate
answered that the account was cold").

### The final number

    EMAILBISON_READY_COHORT = 0

Zero contacts pass every gate today. The binding gate is **account collision**,
and it fails for all 10 for the same self-inflicted reason.

    ceiling after remediation = 10

If the 485 memberships are cleared (delete campaign 485 and its lead attachments,
or otherwise clear the `stopped` status) **and** D1 below is fixed, all 10 pass
every gate. `held:campaign_not_approved` also applies to all 10 today, but that
is the campaign row for the *replacement* not yet existing or being approved —
it resolves as a normal part of building the replacement, not as a contact
exclusion.

**The number is not capped at 10 artificially.** The candidate pool was the whole
estate, not the campaign's record list. The other 41 candidates fail on their
own merits: **none of them carries a current approval on any of em1/em2/em3**
(13-14 carry a stale stamp that does not cover the current text; the remainder
have never been approved), and four additionally have no `em2` step at all.
Nobody was included to raise the number and nobody was excluded to lower it.

### Per-contact exclusion reasons

Every one of the 51 candidates, with the first gate it fails:

| rec hash | in cohort | exclusion reason |
|---|---|---|
| `ff930f49050f` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `d881cb9457f6` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `73636ff041b0` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `90dc872ce83e` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `a02d0a715cb8` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `b15936a38d71` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `b580268f93f2` | yes | **account collision HOLD** (485 membership `stopped`); account additionally TOUCHED, 13 prior emails to a colleague; also D1 |
| `d00a60562edd` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `646934233472` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `73dff24eb5e8` | yes | **account collision HOLD** (485 membership `stopped`); also D1 |
| `9d2802e5f931` | no | **no `em2` step** (cadence runs em1/em3/em5); no current approval; not selected |
| `720c8fc2abd3` | no | **no `em3` step** (em1/em2/em4/em5); no current approval; not selected |
| `0b979dc94800` | no | **no `em3` step** (em1/em2/em4/em5); no current approval; not selected |
| `baf35e64c0dd` | no | **no `em3` step**; record state `held`; no current approval; not selected |
| `2fa23ea5bb68` | no | **no `em2`, no `em3`** (em1/em4/em5); no current approval; not selected |
| `e5fbbe22debe` | no | **no `em2`, no `em3`** (em1/em4/em5); no current approval; not selected |
| `3d9ff6a09535` | no | **no `em1`** (em2/em3/em5); no current approval; not selected |
| `5c2a3cfd7eec` | no | **no `em3`**; no current approval; not selected |
| `0f6272a876ef` (x2 contacts) | no | record state `held`; no current approval; not selected |
| remaining 33 candidates | no | **no current approval fingerprint** on em1/em2/em3, and `blocked:not_selected_for_campaign` |

---

## 4. THE APPROVED COPY

### What is approved

All 30 steps (10 contacts x em1/em2/em3) carry an approval stamped
**2026-09-16T11:37:38+00:00 by the operator** (`zvonimir@...`, operator
authorisation 2026-09-16), applied through `scripts/apply_control_approval.py`
which revoked the prior `claude` stamps first. Each stamp fingerprints the
**campaign-expanded CONTROL step** — `cadence.build(rec, config,
campaign=campaigns.require("productive-email-control-v2"))` — i.e. the
`persona_pain -> comparable_proof -> breakup` sequence.

Checked with the four-argument form
`approval.is_approved(rec, contact_key, step_key, expanded_step)`:
**30 of 30 current.**

### DEFECT D1 — the fingerprint does not cover the text that would be sent

**All 10 contacts, all 30 steps, fail this check.**

    steps compared: 30
    steps where STAGED text != APPROVED text: 30

Worked example, record `b580268f93f2`, step `em1`:

| | value |
|---|---|
| approval stamp fingerprint | `21e1df219ebc31cf` |
| `fingerprint(stored cadence slot)` | `34eb3503e9c4b856` — **does not match** |
| `fingerprint(campaign-expanded step)` | `21e1df219ebc31cf` — matches |
| stored slot subject | *"Custom advertising solutions at &lt;company&gt;"* (generated copy) |
| expanded subject | *"profitability visible on Monday not two weeks late"* (CONTROL copy) |

**The chain, with the two lines that cause it.**

1. `src/approve.py::approve_step` copies the approved step's fields into the
   record slot only when the field is absent:

       for field in ("channel", "subject", "body", "note", "template"):
           if step.get(field) is not None and field not in slot:
               slot[field] = step[field]

   The slot already held `subject` and `body` from an earlier generation run,
   so the CONTROL text was **never written into the slot**. The stamp was
   applied over the expanded text; the slot kept the generated text.

2. `src/bisonfactory.py::_resolve_step_copy`, the no-variant branch, returns
   the **stored slot's** words and checks only that an approval *exists*:

       if (stored_step.get("channel") == "email"
               and stored_step.get("approval")):
           return {"step_key": key, "subject": stored_step.get("subject"),
                   "body": stored_step.get("body")}

   The *variant* branch immediately above it does compare
   `approval.fingerprint(stepped)` against the stored fingerprint and returns
   `None` on mismatch. **The no-variant branch does not.** The guard exists and
   is wired to one of the two branches.

**Net effect.** `bisonfactory._plan` for `productive-email-control-v2` today
returns 10 leads with `missing_copy: []` and `unsupported_copy: []` — it reports
clean — and the words it would stage are the **generated** copy, not the CONTROL
copy the operator approved. A readback would agree with itself. This is the
precise failure the approval system exists to prevent.

This also explains, and inverts, the premise carried into this task. The
three-argument form does **not** agree unconditionally here: it compares the
stamp to the *stored slot*, which has drifted, so it reads `False` for all 30.
The four-argument campaign-expanded form reads `True`. The directive to pass
`campaign=` is right; the stated reason is backwards. The operative fact is that
**neither form is asking what ships** — `_approved_copy` reads a third thing.

`work/approval/CONTROL-COPY-IN-PLACE-2026-09-16.md` states that TASK-210 wrote
the CONTROL text into `em1`/`em2`/`em3` on each record. **Measured against
current state, it did not survive**: every stored slot holds generated copy with
`template: persona_pain` / `comparable_proof` / `breakup` and `generated: true`.

### The approved copy, per contact

This is the text the operator's fingerprints cover — the CONTROL expansion. It
is **not** what `_plan` would stage today (see D1).

Note that `subject_2` and `subject_3` below exist in the approved step but are
**never sent**: the provider sequence references `{SUBJECT_1}` at every step and
`bisonfactory._variables_for` writes `subject_2` and `subject_3` as empty strings
on a threaded sequence. They are recorded here for completeness because the
approval fingerprint does cover them.

Distinct approved subject lines across the cohort:

| variable | distinct values | distribution |
|---|---|---|
| subject_1 | 2 | "profitability visible on Monday not two weeks late" (9), "utilisation and capacity across live projects" (1) |
| subject_2 (not sent) | 2 | "how teams your size handle profitability on Monday" (9), "how teams your size handle utilisation and capacity" (1) |
| subject_3 (not sent) | 1 | "closing the loop" (10) |

### Contact 1 - rec `ff930f49050f`, contact `7d1f45aff0d0`, lead `203708`

persona `economic_buyer` / angle `founder` | domain `c768a0660316` | email `529930f7e146`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:f3fe5a51a2be>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:7ffbaa3b47fb> handles it<br><br>The pattern I see in teams the size of <company:7ffbaa3b47fb> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:7ffbaa3b47fb> today, or have you already put something in place for it? |
| **body_2** | <name:f3fe5a51a2be>, the teams I work with that look most like <company:7ffbaa3b47fb> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:f3fe5a51a2be>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:7ffbaa3b47fb> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `fbf29b5fcc8826d1` | 2026-09-16T11:37:38+00:00 | 106 | 50 | **NO** |
| em2 | `6525482e6fb1c4de` | 2026-09-16T11:37:38+00:00 | 88 | 50 | **NO** |
| em3 | `da5daffddf84327c` | 2026-09-16T11:37:38+00:00 | 83 | 16 | **NO** |

### Contact 2 - rec `d881cb9457f6`, contact `9001fb6df2ea`, lead `203709`

persona `economic_buyer` / angle `operations` | domain `68af8ce671c1` | email `34bc6d04c490`

| field | value |
|---|---|
| **subject_1** | utilisation and capacity across live projects |
| **body_1** | <name:639c0aa08142>, I work with Marketing & Advertising teams on utilisation and capacity across live projects, and I do not know how <company:85edaf487494> handles it<br><br>The pattern I see in teams the size of <company:85edaf487494> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:85edaf487494> today, or have you already put something in place for it? |
| **body_2** | <name:639c0aa08142>, the teams I work with that look most like <company:85edaf487494> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:639c0aa08142>, if utilisation and capacity across live projects is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:85edaf487494> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `9de09ec62943f397` | 2026-09-16T11:37:38+00:00 | 105 | 45 | **NO** |
| em2 | `a686bc66149c62d1` | 2026-09-16T11:37:38+00:00 | 88 | 51 | **NO** |
| em3 | `7c4fb485d1e49d9c` | 2026-09-16T11:37:38+00:00 | 81 | 16 | **NO** |

### Contact 3 - rec `73636ff041b0`, contact `2da1e5722575`, lead `203710`

persona `economic_buyer` / angle `founder` | domain `ceb55a89127b` | email `185d72e07fc8`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | Al, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:b12a0ddfb7aa> handles it<br><br>The pattern I see in teams the size of <company:b12a0ddfb7aa> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:b12a0ddfb7aa> today, or have you already put something in place for it? |
| **body_2** | Al, the teams I work with that look most like <company:b12a0ddfb7aa> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | Al, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:b12a0ddfb7aa> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `2b3df65a205213db` | 2026-09-16T11:37:38+00:00 | 100 | 50 | **NO** |
| em2 | `ae38b02d37feead9` | 2026-09-16T11:37:38+00:00 | 86 | 50 | **NO** |
| em3 | `e54fc381a26025db` | 2026-09-16T11:37:38+00:00 | 81 | 16 | **NO** |

### Contact 4 - rec `90dc872ce83e`, contact `b100051cb1c0`, lead `203711`

persona `economic_buyer` / angle `founder` | domain `4efeb3fe2afd` | email `d6e29c496d88`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:6a4da766522c>, I work with Marketing & Advertising teams on profitability visible on Monday not two weeks late, and I do not know how <company:4d572c8105b1> handles it<br><br>The pattern I see in teams the size of <company:4d572c8105b1> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:4d572c8105b1> today, or have you already put something in place for it? |
| **body_2** | <name:6a4da766522c>, the teams I work with that look most like <company:4d572c8105b1> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:6a4da766522c>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:4d572c8105b1> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `b6c22c2829850fe7` | 2026-09-16T11:37:38+00:00 | 110 | 50 | **NO** |
| em2 | `07f04d3b9ae2b822` | 2026-09-16T11:37:38+00:00 | 89 | 50 | **NO** |
| em3 | `ae5e997babac7076` | 2026-09-16T11:37:38+00:00 | 84 | 16 | **NO** |

### Contact 5 - rec `a02d0a715cb8`, contact `2e616319bb62`, lead `203713`

persona `economic_buyer` / angle `founder` | domain `395be3330be3` | email `985b119c2038`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:01621148306f>, I work with Marketing Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:61ce7d188df9> handles it<br><br>The pattern I see in teams the size of <company:61ce7d188df9> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:61ce7d188df9> today, or have you already put something in place for it? |
| **body_2** | <name:01621148306f>, the teams I work with that look most like <company:61ce7d188df9> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:01621148306f>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:61ce7d188df9> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `268042dcf9fa7a80` | 2026-09-16T11:37:38+00:00 | 106 | 50 | **NO** |
| em2 | `10b0cca71a8dbdff` | 2026-09-16T11:37:38+00:00 | 88 | 50 | **NO** |
| em3 | `2e7fc20d00237f2b` | 2026-09-16T11:37:38+00:00 | 83 | 16 | **NO** |

### Contact 6 - rec `b15936a38d71`, contact `a1d756d28444`, lead `203714`

persona `economic_buyer` / angle `founder` | domain `c3c9e6e49e77` | email `13a755016ef4`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:80fd73d0ae9d>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:351445f3d146> handles it<br><br>The pattern I see in teams the size of <company:351445f3d146> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:351445f3d146> today, or have you already put something in place for it? |
| **body_2** | <name:80fd73d0ae9d>, the teams I work with that look most like <company:351445f3d146> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:80fd73d0ae9d>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:351445f3d146> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `01ef4d85f867dc72` | 2026-09-16T11:37:38+00:00 | 112 | 50 | **NO** |
| em2 | `31abed13468381b8` | 2026-09-16T11:37:38+00:00 | 90 | 50 | **NO** |
| em3 | `0cd74550b8bc2e91` | 2026-09-16T11:37:38+00:00 | 85 | 16 | **NO** |

### Contact 7 - rec `b580268f93f2`, contact `c8b688f83273`, lead `203715`

persona `economic_buyer` / angle `founder` | domain `da9fa0575ce8` | email `eb4715ab1b94`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:c35d6aaf3b38>, I work with Marketing & Advertising teams on profitability visible on Monday not two weeks late, and I do not know how <company:e0be2939d7cc> handles it<br><br>The pattern I see in teams the size of <company:e0be2939d7cc> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:e0be2939d7cc> today, or have you already put something in place for it? |
| **body_2** | <name:c35d6aaf3b38>, the teams I work with that look most like <company:e0be2939d7cc> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:c35d6aaf3b38>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:e0be2939d7cc> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `21e1df219ebc31cf` | 2026-09-16T11:37:38+00:00 | 104 | 50 | **NO** |
| em2 | `1620e148e69a48ab` | 2026-09-16T11:37:38+00:00 | 87 | 50 | **NO** |
| em3 | `5a7b1bb24dd40451` | 2026-09-16T11:37:38+00:00 | 82 | 16 | **NO** |

### Contact 8 - rec `d00a60562edd`, contact `bec85b0b616e`, lead `203716`

persona `economic_buyer` / angle `founder` | domain `500976b76607` | email `0ffd563b26fa`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:366db106f20c>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:dbf581f1525e> handles it<br><br>The pattern I see in teams the size of <company:dbf581f1525e> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:dbf581f1525e> today, or have you already put something in place for it? |
| **body_2** | <name:366db106f20c>, the teams I work with that look most like <company:dbf581f1525e> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:366db106f20c>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:dbf581f1525e> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `ffb28a5dfb4aa656` | 2026-09-16T11:37:38+00:00 | 106 | 50 | **NO** |
| em2 | `323b448843c78887` | 2026-09-16T11:37:38+00:00 | 88 | 50 | **NO** |
| em3 | `94f66c67af236396` | 2026-09-16T11:37:38+00:00 | 83 | 16 | **NO** |

### Contact 9 - rec `646934233472`, contact `7f2b580577dc`, lead `203718`

persona `economic_buyer` / angle `founder` | domain `1203bef7ae16` | email `3c5271f31289`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | <name:0c086cdc772a>, I work with Advertising Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:33201133bcef> handles it<br><br>The pattern I see in teams the size of <company:33201133bcef> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:33201133bcef> today, or have you already put something in place for it? |
| **body_2** | <name:0c086cdc772a>, the teams I work with that look most like <company:33201133bcef> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | <name:0c086cdc772a>, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:33201133bcef> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `3247427ae9069e55` | 2026-09-16T11:37:38+00:00 | 103 | 50 | **NO** |
| em2 | `be78c9f2ed3235dc` | 2026-09-16T11:37:38+00:00 | 87 | 50 | **NO** |
| em3 | `cbcaa4fb52baa484` | 2026-09-16T11:37:38+00:00 | 82 | 16 | **NO** |

### Contact 10 - rec `73dff24eb5e8`, contact `065ea0eefea9`, lead `203809`

persona `economic_buyer` / angle `founder` | domain `ddef577b8d3c` | email `5f883d184ce8`

| field | value |
|---|---|
| **subject_1** | profitability visible on Monday not two weeks late |
| **body_1** | Cj, I work with Marketing Services teams on profitability visible on Monday not two weeks late, and I do not know how <company:913aca5e8dfe> handles it<br><br>The pattern I see in teams the size of <company:913aca5e8dfe> is that the numbers arrive too late to act on. Utilisation and margin are known at the end of the month, which is after the month when something could have been done about them. The work itself is rarely the problem. The visibility into it is.<br><br>Is that roughly how it works at <company:913aca5e8dfe> today, or have you already put something in place for it? |
| **body_2** | Cj, the teams I work with that look most like <company:913aca5e8dfe> tend to arrive at the same place.<br><br>They stop reconciling hours after the fact and start seeing project margin while the project is still running. The change that makes the difference is not a new process for the delivery team, it is that the finance view and the delivery view stop being two different spreadsheets maintained by two different people.<br><br>Would it be useful to see what that looked like for a team your size? |
| **body_3** | Cj, if profitability visible on Monday not two weeks late is not something you are looking at right now, that is a fair answer in itself. I will leave it here.<br><br>If it becomes relevant later, the thing worth knowing is that most teams the size of <company:913aca5e8dfe> start looking at this when a project lands under margin and nobody can say exactly when it went wrong.<br><br>Anything you would want me to send over, or shall I leave it there? |

| step | approval fingerprint | approved at | words | subject len | covers what is sent? |
|---|---|---|---|---|---|
| em1 | `1f89e025105ed381` | 2026-09-16T11:37:38+00:00 | 103 | 50 | **NO** |
| em2 | `204b65b4e21bcca9` | 2026-09-16T11:37:38+00:00 | 87 | 50 | **NO** |
| em3 | `ec77c08dc4cbfd85` | 2026-09-16T11:37:38+00:00 | 82 | 16 | **NO** |

---

## 5. THREADING READINESS

**Source.** `config/clients/productive.yaml`, block `email_sequence` (line 509).

    email_sequence:
      title: Resonate CONTROL
      thread_reply_pattern: [false, true, true]
      steps:
        em1: {order: 1, subject: "{SUBJECT_1}", body: "<p>{BODY_1}</p>", wait_in_days: 3}
        em2: {order: 2, subject: "{SUBJECT_1}", body: "<p>{BODY_2}</p>", wait_in_days: 4}
        em3: {order: 3, subject: "{SUBJECT_1}", body: "<p>{BODY_3}</p>", wait_in_days: 1}

| declared | value |
|---|---|
| step count | **3** |
| `thread_reply_pattern` | **`[false, true, true]`** |
| subject referenced by step 1 | `{SUBJECT_1}` |
| subject referenced by step 2 | **`{SUBJECT_1}`** (not SUBJECT_2) |
| subject referenced by step 3 | **`{SUBJECT_1}`** (not SUBJECT_3) |
| final wait value | **`wait_in_days: 1`** on em3 |

**Built and verified read-only.** `bisonfactory._sequence_steps(config["email_sequence"], cadence.steps_for(campaign))` produces:

| order | step_key | email_subject | email_body | wait_in_days | thread_reply |
|---|---|---|---|---|---|
| 1 | em1 | `{SUBJECT_1}` | `<p>{BODY_1}</p>` | 3 | **false** |
| 2 | em2 | `{SUBJECT_1}` | `<p>{BODY_2}</p>` | 4 | **true** |
| 3 | em3 | `{SUBJECT_1}` | `<p>{BODY_3}</p>` | 1 | **true** |

**VERDICT: the config MATCHES the invariant. No violation.**

- Only the opener owns a subject — em2 and em3 reference `{SUBJECT_1}`.
- No independent `SUBJECT_2` / `SUBJECT_3` anywhere.
- No `"Re: "` simulation anywhere; the provider prepends it.
- Steps 2 and 3 are `thread_reply: true`, same original thread.
- Final wait is 1, which is inert (nothing follows em3) and is 1 rather than 0
  because the provider rejected 0 — this is the check TASK-184 recorded as
  unchecked, and it is now confirmed by the fact that 485 holds 3 stored steps.

Cadence gaps reconcile: `cadence.steps_for` puts em1 on day 1, em2 on day 4,
em3 on day 8 — gaps of 3 and 4, matching the declared waits exactly.

### VIOLATION — campaign 485 as it exists at the provider

`bison.sequence_steps(485)`:

| order | email_subject | thread_reply | wait |
|---|---|---|---|
| 1 | `{SUBJECT_1}` | false | 3 |
| 2 | **`Re: {SUBJECT_2}`** | true | 4 |
| 3 | **`{SUBJECT_3}`** | **false** | 1 |

Two violations in one sequence:

1. **Step 2 carries a `"Re: "` simulation over an independent `{SUBJECT_2}`.**
   Both halves are defects: the provider prepends `Re:` itself, and `SUBJECT_2`
   is a subject a follow-up must not own.
2. **Step 3 is `thread_reply: false` with its own `{SUBJECT_3}`.** A follow-up
   carrying its own prospect-facing subject where a thread reply is expected.

`bison.set_sequence` **appends and cannot replace** (measured 2026-09-13; the
route is GET/HEAD/POST only, PUT is 405, no per-step route exists), so 485
cannot be corrected in place. **Replacement is confirmed as the only remedy.**

Campaign 481 is worse: all five steps `thread_reply: false` with five
independent subjects `{SUBJECT_1}`..`{SUBJECT_5}`.

The guard that would have caught both already exists —
`bisonfactory._sequence_steps` raises `FactoryRefused` on a follow-up that is
not a thread reply and carries a subject distinct from the opener's. 485 and 481
predate it in their stored form.

---

## 6. EXACT EXPOSURE

If a replacement campaign of the declared cohort were built and activated:

| quantity | value |
|---|---|
| leads | **10** |
| steps per lead | **3** (em1, em2, em3) |
| **total emails** | **10 x 3 = 30** |
| campaign cap (`max_emails_per_day` on 485) | 20 |
| **sender 2736 `daily_limit`** | **15** |
| **effective daily cap** | **15/day** — the sender limit binds, not the campaign cap |
| `max_new_leads_per_day` | 20, so all 10 enter sequence on day 1 |
| cadence shape | day 1: 10 emails, day 4: 10 emails, day 8: 10 emails |
| peak day load | 10 emails — under both the 15 sender limit and the 20 campaign cap |
| calendar span | 8 cadence days |
| sending window | Mon-Fri 09:00-17:00 `Europe/Zagreb` (provider schedule id 419 on 485, `status: Not Started`) |

**One sender carries the whole cohort.** 2736 is warming (`warmup_enabled: true`)
with a 15/day limit against a lifetime 1,742 sent. The peak day of 10 is 67% of
that sender's daily limit in a single campaign; the sender is also attached to
481, which if resumed would compete for the same 15.

---

## WHAT MUST HAPPEN BEFORE A CLEAN BUILD

1. **Fix D1.** Either (a) write the CONTROL text into the record slots so the
   stored text and the approved text agree, then re-approve, or (b) make
   `bisonfactory._resolve_step_copy`'s no-variant branch compare
   `approval.fingerprint(stored_step)` against the stored stamp and return
   `None` on mismatch, exactly as the variant branch already does. (b) is the
   guard; (a) is the data. Both are needed — (b) alone turns a silent wrong-copy
   send into a loud refusal, which is correct but leaves the cohort at 0.
2. **Clear D2.** Remove the `stopped` memberships that campaign 485 left on the
   ten leads, so `collision.account_policy` stops returning HOLD for accounts
   that have no real conflict.
3. **Neutralise 481** before anything else is resumed in this workspace. Nine of
   the ten cohort contacts sit in it as `sending_paused` behind a five-step
   non-threaded sequence.
4. **Attach the sender on the campaign row before staging**, per
   `docs/BISON-ARCHIVE-ROOT-CAUSE-2026-09-16.md`, or the replacement will be
   archived within minutes as 484 and 485 were.
5. **Record `b580268f93f2` is not cold.** 13 prior emails to a colleague. Either
   exclude it or ensure no message to it claims first contact.

## REPRODUCTION

Every figure in this document is reproducible read-only:

    py -3 -c "import sys; sys.path.insert(0,'.'); from src.providers import load_env, bison; load_env('config/.env'); print(bison.bound_workspace())"

The gate recomputation, collision reads, plan build and drift measurement were
run as throwaway scripts against `src.store`, `src.eligibility`,
`src.collision` and `src.bisonfactory` with no write path invoked. The
unredacted approved copy is regenerated with
`cadence.build(rec, config, campaign=campaigns.require("productive-email-control-v2"))`;
it is deliberately not carried in this tracked file.
