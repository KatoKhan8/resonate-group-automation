# TASK-546 — Adversarial Review of TASK-425 Branch Head

## Review metadata

    reviewed branch       origin/task-425-one-account-dry-run
    reviewed SHA          2d54e274f1dbf646907073047ede73b5999ab273
    review worktree       .qwen/worktrees/task-546-review
    review date           2026-10-03
    reviewer              Qwen Worker 2 (qwen-worker-2-r9)
    review method         Isolated worktree, read-only, falsification-first
    diff shape            330 files, +1,397 / -63,210 lines

## VERDICT: NOT SAFE TO MERGE

The branch is a **systematic regression of safety gates, operator controls, and
correctness fixes** disguised as a dry-run script. It deletes ~63,000 lines, of
which a large fraction are load-bearing safety mechanisms that master depends on.
The three specific items the task asked about (CLIENT_SUPPLIED, _traces,
killswitch) survive, but the surrounding gate infrastructure does not.

---

## Question 1: Does it weaken any gate, widen any rule, or make any check inert?

**YES, CRITICALLY, IN AT LEAST FOURTEEN DISTINCT WAYS.**

### Finding 1.1 — Operator exclusion entirely removed [CRITICAL]

**Files:** `src/operatorexclusion.py` (DELETED, 791 lines), `src/channels.py`,
`src/eligibility.py`, `src/sequencegate.py`

The entire permanent operator exclusion mechanism is deleted. This is the system
that prevents contacting accounts the operator has permanently refused to sell
to. The removal is comprehensive:

- `src/operatorexclusion.py` — **deleted entirely**
- `src/channels.py` — `OPERATOR_EXCLUDED` status code removed, `_operator_excluded()`
  function deleted, removed from both `email_verdict()` and `linkedin_verdict()`
- `src/eligibility.py` — `_operator_excluded()` removed from `must_not_contact()`,
  `BLOCKED_OPERATOR_EXCLUDED` code removed
- `src/sequencegate.py` — `OPERATOR_EXCLUDED` removed from `BLOCKING_QUALIFICATIONS`

**Effect:** An account the operator has permanently excluded can now pass every
gate in the system. The send path, the channel verdicts, and the sequence gate
all stop asking the question.

### Finding 1.2 — Internal campaign ownership protection removed [CRITICAL]

**Files:** `src/providerwrites.py` (279 lines deleted), `config/internal-campaigns.txt`
(DELETED), `tests/test_the_write_layer_is_sealed.py`

The system that prevented provider writes to manually-run internal Resonate
campaigns is deleted from `providerwrites.py`:
- `require_resonate_os_campaign()` and all ownership classification
  (`RESONATE_OS`, `RESONATE_INTERNAL`, `UNKNOWN_OWNER`) — gone
- `classify_campaign()`, `declared_internal()`, `internal_campaigns_path()` — gone
- `InternalCampaignsUnreadable` exception — gone
- `config/internal-campaigns.txt` — deleted
- The test class `ADestinationThatCannotBeNamedIsRefused` — deleted (this was
  the positive control that proved unowned campaigns were refused)
- The `BoundDestination` mixin — removed from two surviving test classes

**Effect:** A provider write can now target any campaign id, including internal
Resonate campaigns the operator runs manually. The operator's standing decision
("NEVER touch them") is unenforced.

### Finding 1.3 — Sender fingerprint removed from approval [CRITICAL]

**Files:** `src/approval.py`

The approval fingerprint no longer covers WHICH MAILBOX sends:
- `sender_fingerprint()` function — **deleted entirely**
- `SENDER_FIELDS` tuple — deleted
- `NO_SENDER_DECLARED` sentinel — deleted
- `is_approved()` no longer takes `config` parameter, no longer checks sender
- `fingerprint()` no longer includes `ps` (postscript) field

**Effect:** An approval for copy sent from mailbox A now authorizes sending the
same words from mailbox B. This is incident B's exact shape — 64 emails went out
signed with the operator's name from somebody else's mailboxes, which is what
this fingerprint was built to prevent.

### Finding 1.4 — Autonomous production window removed [MODERATE]

**Files:** `src/approval.py`

The time-boxed autonomous production authorization is removed:
- `AUTONOMOUS_PRODUCTION`, `AUTONOMOUS_WINDOWS` — deleted
- `autonomous_window()`, `autonomous_stamp()`, `is_autonomous_production()` — deleted
- `personally_reviewed()` — deleted
- `is_accountable_approver()` simplified to reject everything except operator arms
  and email addresses

**Effect:** Any copy approved during the operator's authorized 48-hour window now
has no valid approver. This may be intentional (the window expired 2026-10-01)
but the DATA and the MECHANISM are both gone, not just expired.

### Finding 1.5 — Client-specific verification policy reverted [CRITICAL]

**Files:** `src/generate.py`, `src/eligibility.py`, `src/channels.py`

Three call sites revert from `lint.sendable(contact, lint.policy_for_record(rec))`
to `lint.sendable(contact)` — the DEFAULTS:

- `src/generate.py:plan()` — sendable filter for contacts
- `src/eligibility.py:_email_checks()` — the send-step gate
- `src/channels.py:email_verdict()` — the channel verdict

**Effect:** Productive moved primary verification to Deliverable and dropped
ContactOut on 2026-09-21. Under the defaults (ContactOut primary), 804 of 1,308
contacts are cleared that the client's own policy refuses. The send gate and the
lint gate now disagree about what "verified" means — which is the exact defect
the fix closed.

### Finding 1.6 — Em dash normalization REVERTED to manufacture banned pattern [CRITICAL]

**Files:** `src/lint.py`

The em dash normalization is changed from `"—": ", "` (safe comma) BACK TO
`"—": " - "` (which produces the exact pattern `copylint.DASH_RE` refuses).

The comment on master explains this was fixed because: "a dash used as
punctuation" was the single most recurrent writer refusal, and the normaliser
was manufacturing the exact pattern the copy lint refuses.

**Effect:** Every email body containing an em dash (which the model produces
despite being told not to) will now be refused by the dash rule AFTER the
normaliser converts it to the banned pattern. The gate fires on the normaliser's
own output.

### Finding 1.7 — Per-step word contract removed [MODERATE]

**Files:** `src/lint.py`

- `STEP_WORD_CONTRACT` — deleted
- `countable_words()` — deleted
- `step_key_of()` — deleted (186 lines)
- `explain_contract()` — deleted
- Import of `writercontract` — removed

**Effect:** The per-step word contract (60-90 for em1-em3, 45-90 for em4-em5)
is no longer enforced. Only the global 40-180 range remains. The writer can
produce a 41-word em1 and pass, even though the contract says 60 minimum.

### Finding 1.8 — Banned internal-routing phrases removed [MODERATE]

**Files:** `src/lint.py`, `prompts/draft.md`

Five banned phrases removed: "economic buyer", "economic buyers",
"financial leaders", "decision maker persona", "would you be interested".

The operator's direction (2026-09-29) was that these are internal routing labels
that must never reach a prospect. The gate and the prompt both no longer enforce
this.

### Finding 1.9 — CTA link presence gate removed [MODERATE]

**Files:** `src/sequencegate.py`

`check_cta()` function — **deleted entirely** (165 lines). This was the gate
that verified the prospect actually sees the CTA link in composed output.

**Effect:** An offer that declares a `cta_link` can now ship emails with no link
at all. The measured defect — five canary emails with no URL passing every rule —
can recur.

### Finding 1.10 — Licensed capability names no longer exempt from claim check [MODERATE]

**Files:** `src/sequencegate.py`, `src/copylint.py`

- `sequencegate.check()` no longer passes `licensed_names` to the claims pack
- `copylint.licensed_names()` — deleted
- `copylint.licensed_capabilities()` — deleted
- `copylint.capability_description_violations()` — deleted (entire TASK-922 gate)
- `untraceable()` no longer exempts licensed names from specifics check

**Effect:** "Report Intelligence" in copy is now refused as an untraceable claim
about the prospect, even though it is the client's own approved capability name.
The ladder requires naming it at rung 4, so em4 becomes unsatisfiable.

### Finding 1.11 — Customer outcome claim detection removed [MODERATE]

**Files:** `src/claims.py` (684 lines deleted)

The entire customer-outcome claim detection system (TASK-914, TASK-915, TASK-916)
is removed:
- `_OUTCOME_VERB_STEMS`, `_VERB_INFLECTION` — deleted
- `customer_outcome_claim()` — deleted
- `_prospect_names()` — deleted
- All semantic class machinery — deleted

**Effect:** "clients using report intelligence have improved resource allocation"
can now ship unrefused. The exact defect TASK-914 was built against recurs.

### Finding 1.12 — max_tokens budget and truncation detection removed [MODERATE]

**Files:** `src/llm.py`, `src/generate.py`

- `max_tokens` parameter removed from ALL model `complete()` methods
- `TruncatedAnswer`, `UnusableAnswer`, `UnreadableAnswer` exception classes — deleted
- `finish_reason == "length"` detection — deleted
- `ScriptedModel.budgets` recording — deleted
- `WRITER_MAX_TOKENS` and the budget forwarding in `_CountedModel` — deleted

**Effect:** A model answer cut off mid-JSON is now returned as if it were whole.
The measured defect — bigfish canary answer cut at character 2724 mid-string —
can recur with no detection.

### Finding 1.13 — USD ceiling and model price check removed from dry run [MODERATE]

**Files:** `scripts/task425_one_account_dry_run.py`

- `--usd-ceiling` argument — deleted
- Model price check (`modelprices.price_for`) — deleted
- Spend ledger per-run reservation — deleted
- The refusal to start with an unpriced model — deleted

**Effect:** The dry run can now spend unlimited USD on model calls with no
ceiling and no price verification. A previous run looped to ~470 model calls
before being killed by hand.

### Finding 1.14 — Store barrier weakened to single directory [LOW-MODERATE]

**Files:** `src/store.py`

The production state barrier now protects only THIS tree's `work/`, not the main
checkout's. `main_checkout_work()`, `protected_directories()`, `_git_common_dir()`,
and `reset_main_work_cache()` are all deleted.

**Effect:** A test running in a worktree can now write to the main checkout's
`work/campaigns.jsonl` without triggering `ProductionStateUnderTest`.

---

## Question 2: Does it silently revert anything on master?

**YES.** Three specific items asked about:

| Item | Status | Detail |
|------|--------|--------|
| CLIENT_SUPPLIED claim-licensing split | **PRESERVED** | Still in `src/claims.py`, `src/packfacts.py` |
| copylint._traces grounding fix | **PRESERVED** | Still in `src/copylint.py:257` |
| Killswitch gates | **PRESERVED** | Untouched in `src/killswitch.py`, `src/executionguard.py` |

But many OTHER things on master are silently reverted:

- **Angles for contact** (`src/generate.py`): `angles_for_contact()` removed,
  reverted to `(client or {}).get("angles")` which returns null because no client
  has a top-level `angles` key. The persona's angles are no longer passed to the
  prompt.
- **Ladder failure detection in plan()** (`src/generate.py`): The block that
  detected ladder ordering failures and added refusal ops is gone.
- **Sequence gate feedback to writer** (`src/generate.py`): `_sequence_gate_failures()`
  and `_ladder_failures()` removed — the writer is no longer told about ladder
  violations.
- **Per-channel all-or-nothing storage** (`src/generate.py`): Reverted to
  all-or-nothing per CONTACT. One bad LinkedIn note discards five clean emails.
- **Sender name** (`config/clients/productive.yaml`): Reverted from "Ivan Mamic"
  to "Ivan" — the full name the sendersignature contract requires.
- **Contact persona in offer selection** (`src/generate.py`): TASK-909 fix
  removed — account-level `persona` field (absent on every real record) defaults
  every record to "champion" again.
- **`client_slug` parameter** (`src/generate.py`): No longer passed to
  `generate_campaign.generate`, so Second Brain retrieval uses the display name
  instead of the canonical slug.
- **Event word plural fix** (`src/claims.py`): "offices in" and "moved to"
  support reverted — the substring bug that made "offices in" not match "office in"
  is back.
- **`send_scope()`** (`src/lint.py`): Removed — the function that scoped checks
  to the actual recipient rather than the whole record.

---

## Question 3: Scope drift and junk

The branch's stated purpose is TASK-425: "one account dry run". The diff includes:

- **~90 task files deleted** from `docs/qwen-tasks/` (TODO, REVIEW, DONE)
- **~25 GLM review documents deleted** from `docs/glm-reviews/`
- **~30 handoff/handoff-adjacent documents deleted** from `docs/`
- **~30 test files deleted** that are unrelated to the dry run
- **Multiple scripts deleted** that are unrelated to the dry run
- **Config files deleted** (`model-prices.yaml`, `operator-exclusions.jsonl`)

The deletion of task files and review documents is scope drift — they are
historical records, not code. The deletion of unrelated tests and scripts
suggests the branch is being used as a vehicle for broad codebase reduction
rather than a focused dry-run improvement.

---

## Question 4: Criterion 4's verifier — actual claims or audit fields?

**The operator's concern is CONFIRMED.** The branch DELETIES the very machinery
that was closing this gap:

- `customer_outcome_claim()` in `src/claims.py` — which checked the ACTUAL
  rendered text for customer-outcome patterns — is deleted (684 lines)
- `capability_description_violations()` in `src/copylint.py` — which checked
  whether capability descriptions traced to licensed `page_text` — is deleted
- `_event_supported()` in `src/claims.py` — which checked whether event claims
  traced to stored facts — is deleted

What remains in `claims.check()` is the per-sentence `is_claim` / `check_sentence`
path, which asks "does this sentence assert something unsupported" — a text-level
check. But the higher-order patterns (customer outcomes, capability descriptions,
event claims with prepositions) that required looking at the WHOLE text rather
than sentence-by-sentence are gone.

**The verifier now checks LESS of the actual rendered claims than master does.**

---

## Summary of dispositions

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1.1 | Operator exclusion removed | CRITICAL | SAFETY REGRESSION |
| 1.2 | Internal campaign ownership removed | CRITICAL | SAFETY REGRESSION |
| 1.3 | Sender fingerprint removed from approval | CRITICAL | SAFETY REGRESSION |
| 1.4 | Autonomous production window removed | MODERATE | Intentional (expired) |
| 1.5 | Client-specific verification policy reverted | CRITICAL | SAFETY REGRESSION |
| 1.6 | Em dash normalization reverted | CRITICAL | SELF-DEFEATING GATE |
| 1.7 | Per-step word contract removed | MODERATE | GATE WEAKENING |
| 1.8 | Banned internal-routing phrases removed | MODERATE | GATE WEAKENING |
| 1.9 | CTA link presence gate removed | MODERATE | GATE WEAKENING |
| 1.10 | Licensed capability names no longer exempt | MODERATE | GATE WEAKENING |
| 1.11 | Customer outcome claim detection removed | MODERATE | GATE WEAKENING |
| 1.12 | max_tokens budget and truncation detection removed | MODERATE | GATE WEAKENING |
| 1.13 | USD ceiling removed from dry run | MODERATE | COST CONTROL REMOVED |
| 1.14 | Store barrier weakened | LOW-MODERATE | ISOLATION WEAKENED |

---

## Recommended Claude action

**DO NOT MERGE THIS BRANCH.** The branch is not safe to merge to master. It
removes at least four critical safety mechanisms (operator exclusion, internal
campaign protection, sender fingerprint, client-specific verification) and
reverts multiple correctness fixes. The three items the task specifically asked
about survive, but they are islands in a sea of regression.

If the intent was to simplify the dry-run script, the branch has overshot by
~60,000 lines of safety infrastructure that the rest of the system depends on.
