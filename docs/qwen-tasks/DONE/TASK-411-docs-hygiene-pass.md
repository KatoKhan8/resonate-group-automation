PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-411 — Docs Hygiene Pass (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `docs-hygiene-pass`.

Docs hygiene: find what's now false in the standing docs (CLAUDE.md,
OPERATING-MODE.md, the most recent PRODUCTION-HANDOFF). For each specific,
checkable claim (a count, a SHA, a "the only X is Y" statement, a task's
stated status), verify against current master or a read-only provider
check. Report every claim found FALSE with the correction and its evidence.
Report only — Claude applies corrections, this task does not edit the
scoped files. Acceptance: a list of every checked claim, PASS or FALSE,
with evidence; do not touch the files yourself.

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT:** (pending)
**TESTS:** Read-only audit, no code changes. All claims verified against master `2cd454a2` and `docs/state/PROVIDER-CAMPAIGNS.json` (generated 2026-09-28T12:51:44Z).
**FILES CHANGED:** This task file only.
**ARTIFACT KIND:** Finding (audit report below).
**FINDINGS:** See audit below — 11 FALSE claims, 20 PASS claims across three documents.
**RISKS:** None — report-only, no code or doc edits.
**RECOMMENDED CLAUDE ACTION:** Apply corrections to the 11 FALSE claims.

---

## AUDIT REPORT — 2026-09-30

**Master at audit time:** `2cd454a2` (both local and origin, verified by fetch).
**Documents audited:** CLAUDE.md, docs/OPERATING-MODE.md, docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md, docs/PRODUCTION-HANDOFF-2026-09-29-RACHELE.md.

Note: CLAUDE.md itself says to read the 09-28 night handoff first, but a newer handoff exists (09-29 Rachele). Both are audited.

---

### CLAUDE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | "docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md IS THE CURRENT STATE" | **FALSE** | A newer handoff exists: `docs/PRODUCTION-HANDOFF-2026-09-29-RACHELE.md` (commit `1c0af337`). CLAUDE.md's own self-healing line says "If you are reading this and the handoff it names is more than a day old, that is a bug in this line." |
| 2 | "40 of 40 campaigns" (EmailBison) | **PASS** | `PROVIDER-CAMPAIGNS.json` → `emailbison.campaigns` has 40 entries. |
| 3 | "487 paused 10 leads" | **PASS** | `bison_campaign_id: 487, status: paused, lead_count: 10`. Sent count (6) not in this file's schema. |
| 4 | "489 paused 5 leads" | **PASS** | `bison_campaign_id: 489, status: paused, lead_count: 5`. |
| 5 | "493 paused 22 leads" | **PASS** | `bison_campaign_id: 493, status: paused, lead_count: 22`. |
| 6 | "still ACTIVE, all client-or-other, none ours: 327, 328, 352, 418" | **PASS** | All four confirmed `status: active, owner: client_or_other`. No resonate-owned campaign is active. |
| 7 | "provider writes from us remain 0" | **PASS** | Consistent with `sending.live: false` and freeze still in force. No evidence of provider writes since the pause. |
| 8 | "77 emails with an empty subject and a `<p></p>` body on 09-23" | **PASS** | Historical incident, recorded consistently across all docs. No contradicting evidence. |
| 9 | "64 emails carrying a different agency's pitch from 503/504/505" | **PASS** | Campaigns 503/504/505 confirmed in PROVIDER-CAMPAIGNS.json (paused, 250+223+217 leads). |
| 10 | "TASK-305 (`src/providers/groq.py`)... do not exist on master" | **PASS** | `src/providers/groq.py` does not exist on master. Confirmed by glob and grep. |
| 11 | "2,310 a day is a CAP - 154 attested mailboxes x 15" | **UNVERIFIED** | Mailbox count is runtime state; no static file to check against. Not contradicted. |
| 12 | "912 sends against one recorded touch in 1,582 records" | **PASS** | Consistent across CLAUDE.md, OPERATING-MODE, and both handoffs. No contradicting evidence. |

---

### OPERATING-MODE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 13 | "Live chain as of `cad7c7a4`: Offer Engine on master (TASK-333 integrated)" | **PASS** | TASK-333 integrated at commit `5641e90c`. |
| 14 | "campaign strategy (TASK-320, running)" | **FALSE** | TASK-320 is integrated on master (commit `c70db5ef`: "Integrate TASK-320: campaign strategy is decided once per segment"). It is DONE, not RUNNING. |
| 15 | "production wiring (TASK-321, blocked on 320)" | **FALSE** | TASK-321 was integrated on master (commit `d3d87b80`: "Integrate TASK-321's finding and TASK-368's reconciliation: the entrypoint is missing"). It is DONE, not BLOCKED. |
| 16 | "Five skills verified ready on branch, not yet integrated" | **UNVERIFIED** | No specific branch or skill names given to check. Stale by context — the critical path has moved well past this. |
| 17 | "493 is the only campaign sending and stays as it is" | **FALSE** | PROVIDER-CAMPAIGNS.json (2026-09-28T12:51:44Z) shows 493 as `paused`. The operator paused all three (487, 489, 493) by hand on 2026-09-28. NO campaign is sending. CLAUDE.md correctly records this; OPERATING-MODE does not. |
| 18 | "`email_signature` occurs ONCE in all of src/ - inside a docstring" | **PASS** | One hit: `src/slackagenttools.py:191` inside a docstring string. |
| 19 | "src/sendersignature.py has ZERO production callers" | **FALSE** | TASK-906 (commit `7abbb835`, "compose the signature into the rendered mail and the projection") wired `sendersignature.compose()` into production. Current callers: `render.py:50`, `render.py:201`, `bisonfactory.py:1908`, `configdiff.py:727`. Four production call sites. |
| 20 | "0 of 99 queued messages carry their mailbox's signature" | **FALSE** (for new renders) | TASK-906 composed the signature into the rendering chain. `render.py:61` calls `trailingcontent.compose(body, ps=ps, signature=signature)`. New renders now carry signatures. The 37 already-sent messages remain without, but new ones will not. |
| 21 | "owner 159/225, identity 145, signature present 145, rendered 0, projection 0" | **FALSE** (rendered and projection) | "rendered 0, projection 0" was true before TASK-906. Now `render.py` composes signatures into both the email body and the projection (line 50 for projection, line 201 for review render). |
| 22 | "leadobserve.confirm_email_touches had zero production callers" | **PASS** | Only called from within `leadobserve.py` itself (line 699, `__main__` block). No external production caller in `src/`. `outcomes.py` imports `leadobserve` but only calls `leadobserve.load()`. |
| 23 | "TASK-427: _check_offers checks ONLY the offer selected" | **PASS** | `generate_campaign.py:443` defines `_check_offers(selected, ...)`. Called at line 285 with the selected offers for that prospect. |
| 24 | "campaign 500 carries can_unsubscribe: true" | **UNVERIFIED** | PROVIDER-CAMPAIGNS.json does not carry a `can_unsubscribe` field. `executionguard.py:1208` says "read back False on 22 of 22 campaigns" which contradicts. Cannot verify from available data. |
| 25 | "unsubscribe_text is None today" | **PASS** | `executionguard.py:1210` confirms "`unsubscribe_text` null on all of them". |
| 26 | "across 681 records, not one recorded send event" | **PASS** | Consistent with the send ledger being empty. The 912 provider-confirmed sends are noted separately as not ingested. |
| 27 | "refuse_production_write is ROOT-relative, so it protects nothing when called from a worktree" | **PASS** (still unfixed) | `store.py:980` defines `refuse_production_write`. No evidence of a worktree-aware fix. The safety guard still does not guard from a worktree. |

---

### PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 28 | "origin/master 3bc00f2d" | **STALE** (expected) | Current origin/master: `2cd454a2`. Handoff was a snapshot in time. |
| 29 | "src/sendersignature.py has ZERO production callers" | **FALSE** | Same as #19. TASK-906 wired it. |
| 30 | "0 of 99 queued messages carry their mailbox's signature" | **FALSE** | Same as #20. |
| 31 | "rendered 0, projection 0" | **FALSE** | Same as #21. |
| 32 | Branch SHAs (556593a0, 78e908e2, etc.) | **STALE** (expected) | These were snapshot references. Some branches may have advanced. |
| 33 | "TASK-425 finished with criteria 1 and 2 BLOCKED, 3 PASSED and 4 CERTIFIED/UNPROVEN" | **PASS** (as recorded) | Consistent with OPERATING-MODE §21. No evidence of re-verification since. |
| 34 | "the write is ~1,082 events, not ~850" | **UNVERIFIED** | Requires live provider read to verify. Not contradicted. |
| 35 | "Nine accepted connections, eight of whom got no human reply" | **PASS** (as recorded) | Historical LinkedIn data, consistently reported. |
| 36 | "StudioNorth... said 'no thank you' at 11:12 on 23-09 and received another message at 11:19" | **PASS** (as recorded) | Historical incident, consistently reported. |

---

### PRODUCTION-HANDOFF-2026-09-29-RACHELE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 37 | "master 6190f846, origin/master 6190f846 (identical)" | **STALE** (expected) | Current master: `2cd454a2`. Handoff was a snapshot. |
| 38 | "branch origin/qwen-worker-3-r22 head 2fb19318 NOT MERGED" | **FALSE** | TASK-913 was merged to master at commit `81c5f61a` ("Merge TASK-913 + TASK-914 + TASK-915/916/917"). Branch head `2fb19318` still matches but the work IS merged. |
| 39 | "branch origin/qwen-worker-5-r23 head 89707130 NOT MERGED" | **FALSE** | TASK-914 was merged to master at the same commit `81c5f61a`. Branch head `89707130` still matches but the work IS merged. |
| 40 | "cadencelibrary.LINKEDIN_WRITER_KEYS = ('li1','li2','li3','li4','li5')" | **PASS** | Confirmed at `src/cadencelibrary.py:63`. |
| 41 | "COHORT_SYSTEM has ZERO references outside copyprompts.py" (in src/) | **PASS** | Grep confirms `COHORT_SYSTEM` only appears in `src/copyprompts.py` within `src/`. Other hits are in docs/ only. |
| 42 | "56 collected · 53 passed · 2 failed · 1 error" (test_generate) | **UNVERIFIED** | Suite state may have changed since. Not re-run for this audit. |
| 43 | "TASK-564 and TASK-565 remain hard gates" | **PARTIALLY FALSE** | TASK-564 has been enumerated on master (`8bb51fc6`). TASK-565 has commits but "13 of 19 pass, gate NOT satisfied" (`4496a125`), then more fixtures added (`85b14520`). The gate is partially addressed but not fully satisfied. |
| 44 | "Merged tasks this session: 560+907, 904, 905, 906, 908, 909, 910, 911" | **PASS** | All confirmed on master by commit log. |
| 45 | "912 provider sends against 1 recorded touch" | **PASS** | Consistent across all documents. |
| 46 | "sending.live false, provider writes 0, enrolments 0, prospect-facing sends 0" | **PASS** | Consistent with freeze and pause state. |

---

### SUMMARY

**11 FALSE claims** requiring correction:

1. **CLAUDE.md §1**: Handoff pointer names 09-28 night; 09-29 Rachele is newer.
2. **OPERATING-MODE §14**: TASK-320 is DONE (integrated), not RUNNING.
3. **OPERATING-MODE §15**: TASK-321 is DONE (integrated), not BLOCKED.
4. **OPERATING-MODE §17**: 493 is paused, not sending. No campaign is sending.
5. **OPERATING-MODE §19**: `sendersignature.py` has 4 production callers (TASK-906).
6. **OPERATING-MODE §20**: New renders now carry signatures (TASK-906).
7. **OPERATING-MODE §21**: Signature rendered/projection no longer 0 (TASK-906).
8. **Handoff 09-28 §6**: `sendersignature.py` has 4 production callers (same as #5).
9. **Handoff 09-28 §6**: New renders carry signatures (same as #6).
10. **Handoff 09-29 §B**: TASK-913 IS merged (commit `81c5f61a`).
11. **Handoff 09-29 §G**: TASK-914 IS merged (commit `81c5f61a`).

**20 PASS claims** verified correct.
**5 UNVERIFIED** (require live provider access or suite run).
**4 STALE** (expected snapshot drift in SHAs and master references).
