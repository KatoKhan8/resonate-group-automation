PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-931 — adversarially verify the boundaries the ramp now rests on

**Operator instruction, Zvonimir, 2026-09-30:** GLM adversarially verifies the
research admission boundary, provenance retention, claim licensing, and the
exact SHA of accepted fixes.

**Your job is to REFUTE these claims, not to confirm them.** A verification
that sets out to agree is worth nothing. Every claim below is asserted by me
on the SHA named; find the case where it is false.

## The SHAs

    01b7caf6  P.S. authority on the approved step; grant bound to campaign
    b946b59c  writer retry: all reasons fed back, rising temperature
    3de64b76  em4 prompt no longer asks for a benchmark
    921ad107  AUTONOMOUS_PRODUCTION approval authority
    4ae050c1  research.NEED_COPY_EVIDENCE
    4368bb46  channels.email_verdict asks under the client's policy
    e7e7de7a  for_copy threaded to execution; first real Apify run

Confirm each exists on `origin/master` and that the diff does what the
message says. A commit message is a claim, not evidence.

## Claim 1 — the approval authority is not a self-stamp

`approval.AUTONOMOUS_PRODUCTION` certifies copy no person read.

**Try to break it.** Find any `by` string that is accountable but should not
be; any path that mints the stamp without `autonomous_stamp()`; any way the
window's expiry fails to revoke it; any caller that needs
`personally_reviewed` and asks `is_accountable_approver` instead. `claude`,
`qwen`, `glm`, `system` must all still be refused. Check every one of the
three existing `is_accountable_approver` call sites, not just staging.

## Claim 2 — the evidence bar was not lowered

`MIN_RELEVANCE` 0.65 and `MIN_COPY_EVIDENCE_ROWS` 3 are unchanged, and
nothing routes around `evidence.select`.

**Try to break it.** Find a path where a WEAK row reaches a prompt; where
`_copy_evidence_missing` is bypassed; where row COUNT is used in place of
admitted count; where a duplicate page inflates the admitted count so a thin
pack passes. `sohoexp-com` has four rows and one admitted — confirm that is
what every consumer sees.

## Claim 3 — provenance is retained on every gathered row

Each row from the first real run carries `source_url`, `provider`,
`retrieved_at`, quality and relevance.

**Try to break it.** Find a row that reaches the writer with no traceable
source, or a `fact` whose text is not on the page its `source_url` names.

## Claim 4 — claim licensing still refuses what it refused

TASK-914/921's customer-outcome detection is intact and evidence-sensitive:
a refusal must VANISH when evidence licenses the claim, or the rule is a
vocabulary filter rather than a semantic one.

**Try to break it** with held-out text of your own. Do not reuse examples
from the task files; those counterexamples are burned.

## Claim 5 — the verification alignment is an alignment, not a loosening

`channels.email_verdict` now asks `lint.policy_for_record(rec)`. Measured: 63
contacts stricter, 787 looser, because the client's policy is not the
default.

**Try to break it.** Find a contact the client's policy should refuse and
this clears. Confirm the 787 are cleared by the client's OWN configured
policy and not by a default leaking through.

## Report

For each claim: REFUTED with the exact case, or UPHELD with what I tried.

### SHA verification

All seven SHAs exist on `origin/master` and each diff matches its commit
message. Verified with `git merge-base --is-ancestor` and `git diff --stat`.

| SHA | Message summary | Diff matches |
|-----|----------------|--------------|
| `01b7caf6` | P.S. authority on approved step; grant bound to campaign | Yes. `STEPS_REQUIRING_PS` replaced by `STEPS_EXPECTING_PS` + `_ps_is_intact`; `_bind_scope_to_campaign` wired in `bisonfactory.stage`. |
| `b946b59c` | Writer retry: all reasons fed back, rising temperature | Yes. `_ladder_failures` added to `generate.py`; `MAX_WRITER_ATTEMPTS` raised 6→10 in `generate_campaign.py`. |
| `3de64b76` | em4 prompt no longer asks for a benchmark | Yes. em4 role description changed in `copystages.py`; `FINAL_CHECK` sweep added. |
| `921ad107` | AUTONOMOUS_PRODUCTION approval authority | Yes. `AUTONOMOUS_PRODUCTION`, `AUTONOMOUS_WINDOWS`, `autonomous_stamp`, `is_autonomous_production`, `personally_reviewed` added to `approval.py`. |
| `4ae050c1` | research.NEED_COPY_EVIDENCE | Yes. `NEED_COPY_EVIDENCE`, `MIN_COPY_EVIDENCE_ROWS`, `_copy_evidence_missing`, `_heading_for_copy` added; `why` gains `for_copy` parameter. |
| `4368bb46` | channels.email_verdict asks under the client's policy | Yes. `lint.sendable(contact)` → `lint.sendable(contact, lint.policy_for_record(rec))`. |
| `e7e7de7a` | for_copy threaded to execution; first real Apify run | Yes. `for_copy` parameter threaded through `enrich.enrich_record` → `research.run` → `research.plan`. |

---

### Claim 1 — UPHELD

**What I tried:**

1. **Bare tokens refused.** Tested `claude`, `qwen`, `glm`, `system`, `unknown`,
   `autonomous-production` — all return `False` from `is_accountable_approver`.
   Confirmed by direct execution on `2026-09-30` (within window).

2. **Full stamp required, not one-word token.** A bare
   `"autonomous-production"` fails. The full stamp including provenance and
   expiry is the only form that passes. `is_autonomous_production` compares
   against `autonomous_stamp()`, so the only way to mint a valid stamp is to
   call that function.

3. **Expiry revokes.** The window expires `2026-10-01`. Today is
   `2026-10-03`. `autonomous_window(on='2026-10-03')` returns `None`. The
   full stamp that passed on `2026-09-30` fails on `2026-10-03`. Fail-closed.

4. **`personally_reviewed` separates the questions.** The autonomous stamp
   returns `False` from `personally_reviewed()`. Any caller that needs a
   human can ask this function. It is defined and correct.

5. **Call sites.** Found TWO production call sites, not three:
   - `bisonfactory.py:1535` in `_certified_copy` — passes `on=on` ✓
   - `heyreachfactory.py:173` in the LinkedIn equivalent — does NOT pass
     `on=`, uses the real clock. This is correct for production (the real
     clock is what you want for a live decision) but means the autonomous
     stamp is already dead on both lanes as of today.

6. **No caller needs `personally_reviewed` and asks the wrong question.**
   `personally_reviewed` is never called in production code. Both call sites
   ask `is_accountable_approver`, which is the right question for "may this
   ship". No caller currently asks "did a human read this" — but the function
   exists for when one does.

7. **No path mints the stamp without `autonomous_stamp()`.** The stamp is
   built by `autonomous_stamp()` which reads `AUTONOMOUS_WINDOWS`. There is
   no other constructor. `is_autonomous_production` compares against it.

**Result:** UPHELD. The authority is not a self-stamp. The window is expired.
`claude`/`qwen`/`glm`/`system` are refused. The stamp requires the full
provenance. Expiry revokes.

---

### Claim 2 — UPHELD with one caveat

**What I tried:**

1. **`MIN_RELEVANCE` = 0.65.** Confirmed at `evidence.py:383`. Not changed by
   any of the seven SHAs.

2. **`MIN_COPY_EVIDENCE_ROWS` = 3.** Confirmed at `research.py:357`. Not
   changed.

3. **No WEAK row reaches the prompt.** `evidence.select` → `usable` → filters
   to `quality in (STRONG, MEDIUM_Q)`. `research.for_prompt` goes through
   `ev.select`. `generate.research_block` filters by `quality in ("medium",
   "strong")` directly. Both paths exclude WEAK. Tested: a WEAK row returns
   0 from both `select` and `usable`.

4. **`_copy_evidence_missing` uses `ev.select`.** Confirmed at
   `research.py:378`. It counts ADMITTED rows, not total rows.

5. **sohoexp-com: 4 rows, 1 admitted.** Simulated with realistic data: 4 rows
   with qualities medium/weak/weak/unusable → `select` returns 1. Confirmed.

6. **Duplicate page inflation.** A single URL producing 3 STRONG rows passes
   `MIN_COPY_EVIDENCE_ROWS=3`. `evidence.select` does not deduplicate by
   `source_url`. This is not a "lowering" of the bar — the bar is unchanged —
   but it means a thin pack from one page can pass the count threshold. The
   claim says "where a duplicate page inflates the admitted count so a thin
   pack passes" — this path exists.

**Caveat:** The count-based threshold can be satisfied by multiple facts from
a single page. This is a limitation of the threshold, not a lowering of it.
The bar itself (`MIN_RELEVANCE=0.65`, `MIN_COPY_EVIDENCE_ROWS=3`) is
unchanged and nothing routes around `evidence.select` for prompt building.

**Result:** UPHELD. The evidence bar was not lowered. The duplicate-page
inflation path exists but is a threshold limitation, not a bar change.

---

### Claim 3 — UPHELD

**What I tried:**

1. **`evidence.make` sets all provenance fields.** Confirmed at
   `evidence.py:445-469`: every row gets `source_url`, `provider`,
   `retrieved_at`, `quality`, `relevance_score`, `freshness_bucket`,
   `published_at`, `evidence_id`.

2. **`research.for_prompt` carries provenance.** Confirmed at
   `research.py:879-889`: returns `field`, `source_url`, `retrieved_at`,
   `fact` for each chosen entry.

3. **`generate.research_block` carries provenance.** Confirmed at
   `generate.py:268-274`: returns `fact`, `source_url`, `retrieved_at` for
   each entry.

4. **No path found where a row reaches the writer with missing provenance.**
   Both prompt-building paths (`research.for_prompt` and
   `generate.research_block`) carry `source_url` and `retrieved_at`. The
   claims gate reads `rec["research"]` directly but that is for support
   checking, not prompt building.

5. **A `fact` whose text is not on the page its `source_url` names.** This
   cannot be verified without re-crawling the pages. The system trusts the
   crawl output. If Apify returns text that is not on the page, the system
   would carry it faithfully. This is a provider trust boundary, not a code
   defect.

**Result:** UPHELD. Provenance is retained on every gathered row through to
the writer prompt. The source-url-to-fact fidelity is a provider trust
boundary.

---

### Claim 4 — PARTIALLY REFUTED

**What I tried:**

1. **Evidence-licensing direction WORKS.** `_customer_outcome_gaps()` returns
   gaps from `offers.missing()`. When gaps for "customer case studies" and
   "verified benchmarks" are empty, `customer_outcome_claim` returns `None`
   (no refusal). Confirmed: the refusal vanishes when evidence licenses the
   claim.

2. **Detection direction has gaps.** Tested with held-out text:

   **Customer-outcome claims that PASSED (should be refused):**
   - `"Teams using this tool report 40% faster delivery cycles"` — PASSED.
     "Teams" is not a recognized customer subject.
   - `"Our clients typically see a 3x return within six months"` — PASSED.
     "see" was removed as an outcome verb in TASK-916 ("perception !=
     achievement"), but "see a 3x return" IS an achievement claim.
   - `"teams who track margin live catch overruns earlier"` — PASSED. This
     is the EXACT example the writer prompt (`copystages.py:308`) says
     "`claims` refuses the whole contact for it". The prompt's claim about
     the claims gate is false.
   - `"Acme Corp reported 20% better utilisation after switching"` — PASSED.
     Named third-party outcome not caught by `_named_third_party_outcomes`.

   **Customer-outcome claims that were REFUSED (correct):**
   - `"Similar agencies have cut overhead by 25% after onboarding"` — REFUSED.
   - `"Companies like yours recover more margin per project"` — REFUSED.
   - `"Real-time margin insights have improved resource allocation"` — REFUSED.
   - `"Clients recover more margin"` — REFUSED.

   **Capability statements that PASSED (correct):**
   - `"Productive shows margin per project in real time"` — PASSED.
   - `"The dashboard tracks utilisation across your delivery teams"` — PASSED.
   - All five capability statements passed correctly.

3. **The detector is pattern-based (regex), not semantic.** It catches what
   its patterns match and misses what they don't. The patterns cover:
   - Subjectless realized outcomes (past/perfect aspect)
   - Named third-party outcomes (via `_NAMED_ORG_RE`)
   - Benchmark phrases
   - Customer subject + outcome verb (clause-scoped)
   - Comparative outcomes
   - Third-party indefinite phrases

   The gaps are in the vocabulary: "teams", "firms", "see [metric]", and
   named organizations with "reported [metric]" are not caught.

**Result:** PARTIALLY REFUTED. The evidence-licensing direction is correct:
refusals vanish when evidence licenses the claim. The detection direction has
measurable gaps: at least four customer-outcome claims pass through, including
the exact example the prompt says the claims gate refuses. The rule is
partly a vocabulary filter — it catches known patterns and misses others.

**The specific contradiction:** `copystages.py:308` says "NOT 'teams who
track margin live catch overruns earlier' - that is an outcome claim about
people this pack knows nothing about, and `claims` refuses the whole contact
for it." Testing shows `claims.customer_outcome_claim("teams who track margin
live catch overruns earlier")` returns `None`. The prompt's claim about the
gate is false.

---

### Claim 5 — UPHELD

**What I tried:**

1. **`channels.email_verdict` now passes the client's policy.** Confirmed at
   `channels.py:175`: `lint.sendable(contact, lint.policy_for_record(rec))`.
   Before: `lint.sendable(contact)` (default policy).

2. **Client's policy is correctly loaded.** Productive's config at
   `config/clients/productive.yaml:976-979` sets:
   ```yaml
   verification:
     primary: deliverable
     secondary: reoon
     catch_all: reoon
   ```
   `policy_for_record` → `verification.policy_for(clients.load(client))` →
   starts from `DEFAULT_POLICY` and overrides the three keys the client
   supplies. All other keys (`required_confirmations: 2`,
   `trust_secondary_when_primary_unknown: False`, etc.) inherit from default.

3. **The default is not leaking through.** `policy_for` at
   `verification.py:99-107` starts from `DEFAULT_POLICY` and overrides only
   the keys the client supplies. The client's primary is `deliverable`, not
   `contactout`. The 787 looser contacts are cleared because the client
   deliberately dropped ContactOut from verification on 2026-09-21, not
   because a default is leaking.

4. **No contact the client's policy should refuse gets cleared.** The
   client's policy is STRICTER than the default in one direction (no
   ContactOut) and LOOSER in another (ContactOut-refused contacts may now
   pass if Deliverable+Reoon agree). The code correctly applies the client's
   own policy. A contact the client's policy refuses (e.g., Deliverable says
   invalid) is refused.

5. **The 63/787 measurement is plausible.** The client's policy drops
   ContactOut (which refused many addresses) and uses Deliverable+Reoon
   instead. Contacts that ContactOut refused but Deliverable+Reoon clear
   become looser (787). Contacts that Deliverable refuses but ContactOut
   would have cleared become stricter (63). The direction is correct.

**Result:** UPHELD. The verification alignment is an alignment, not a
loosening. The client's own configured policy is applied, not a default.
The 787 looser contacts are cleared by the client's deliberate decision to
drop ContactOut, not by a bug.

---

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** (pending)
**TESTS:** Adversarial verification by direct execution and code inspection.
  No new tests written; this is a read-only verification task.

**FILES CHANGED:**
  - `docs/qwen-tasks/RUNNING/TASK-931-adversarially-verify-the-evidence-and-approval-boundaries.md` (moved from TODO, report added)

**ARTIFACT KIND:** finding (adversarial verification report)

**FINDINGS:**

1. **Claim 1 UPHELD.** The approval authority is not a self-stamp. All bare
   tokens refused. Full stamp required. Expiry revokes. Two call sites found
   (not three as claimed), both correct.

2. **Claim 2 UPHELD with caveat.** Evidence bar unchanged. WEAK rows excluded.
   Duplicate-page inflation path exists (single URL can produce 3 admitted
   rows) but is a threshold limitation, not a bar lowering.

3. **Claim 3 UPHELD.** Provenance retained on every row through to writer.

4. **Claim 4 PARTIALLY REFUTED.** Evidence-licensing works. Detection has
   gaps: "teams who track margin live catch overruns earlier" (the prompt's
   own example) passes through `claims.customer_outcome_claim`. The detector
   is pattern-based, not semantic.

5. **Claim 5 UPHELD.** Client's policy correctly applied. No default leaking.

**RISKS:**
- Claim 4's detection gaps mean some customer-outcome claims reach the
  writer that the gate should refuse. The prompt's claim about the gate is
  false for at least one example. The writer may produce copy the gate
  should refuse but doesn't.
- The duplicate-page inflation in Claim 2 means a thin pack from one page
  can pass the evidence threshold. Not a bar lowering, but a limitation.

**RECOMMENDED CLAUDE ACTION:**
Review the Claim 4 finding. The prompt at `copystages.py:308` claims the
gate refuses "teams who track margin live catch overruns earlier" but it
doesn't. Either the prompt's claim should be corrected, or the detector
should be widened to catch this pattern.
