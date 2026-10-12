# GLM Independent Verification: TASK-358

**Review target:** TASK-358 - CheapVerifier exists on a branch and is not in the waterfall  
**Branch reviewed:** `origin/qwen-worker-3-r9-task285`  
**Branch HEAD SHA:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`  
**TASK-358 artifact commit:** `e19b7b94b` (move to REVIEW)  
**Core work commit:** `b27c8452b` (cherry-pick)  
**Enrich fix commit:** `5f6d83d78` (COSTS/CALL_STAGE registration)  
**Review performed:** 2026-10-12  
**Reviewer:** GLM (independent verification layer)  
**Worktree:** `glm-verify-task-358` at `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (detached HEAD)

---

## Summary

**DISPOSITION: REWORK — DISCONNECTED**

TASK-358 successfully registered CheapVerifier in the email_verification waterfall's GLOBAL table and added the enrich.COSTS/CALL_STAGE entries. The tests pass. However, **CheapVerifier has zero production callers** — `src/verification.py` does not import it, does not list it in `verifiers()`, and does not invoke it. The module exists, the waterfall knows about it, but no production code path calls `cheapverifier.verify_single()` through the waterfall. This is the exact defect documented in QWEN.md: "Existence is not function... a thing computed correctly that nothing downstream reads."

---

## Findings

### Finding 1: Artifact exists and does what the result block claims — PARTIALLY VERIFIED

**Status:** PARTIALLY VERIFIED

The artifacts exist:
- `src/providers/cheapverifier.py` (1,142 lines) — cherry-picked from `worktree-agent-a9fe2f7a7ad9343aa`
- `src/waterfall.py` — CHEAPVERIFIER constant added, EMAIL_VERIFICATION entry added (second position), COST_UNITS entry added
- `src/enrich.py` — `COSTS["cheapverifier-verify"] = 1` and `CALL_STAGE["cheapverifier-verify"] = "email_verification"` added
- `tests/test_cheapverifier_is_part_of_the_waterfall.py` — 10 tests, all green

The waterfall order is correct:
```
email_verification order: ['contactout', 'cheapverifier', 'deliverable', 'reoon']
ContactOut index: 0
CheapVerifier index: 1
```

ContactOut is first (PROVIDER-ROUTING-POLICY.md invariant holds). CheapVerifier is second. The tests prove registration, ordering, and ledger recording.

**However:** The result block claims "DONE, artifact verified" but does not verify the production caller chain. The artifact is registered but not consumed.

**Evidence:**
```bash
$ git log --diff-filter=A --all -- src/providers/cheapverifier.py
commit b27c8452bb04394dcdd3b702b0de5b3a2b7102d8
Author: Zvonimir Beslic <zvonimir@resonategroup.co>
Date:   Sun Sep 27 15:51:33 2026 +0200

    TASK-358: CheapVerifier cherry-picked into the email_verification waterfall
```

```bash
$ py -3 -c "import sys; sys.path.insert(0, '.'); from src import waterfall as W; \
  d = W.describe(); provs = [p['provider'] for p in d[W.EMAIL_VERIFICATION]['providers']]; \
  print('email_verification order:', provs)"
email_verification order: ['contactout', 'cheapverifier', 'deliverable', 'reoon']
```

```bash
$ py -3 -m unittest tests.test_cheapverifier_is_part_of_the_waterfall -v
Ran 10 tests in 0.001s
OK
```

---

### Finding 2: Existence is not function — DISCONNECTED

**Status:** DISCONNECTED — REWORK REQUIRED

**The critical defect:** `src/verification.py` does not import CheapVerifier. The production caller chain is broken.

**Evidence:**
```bash
$ grep -rn "from.*cheapverifier\|import.*cheapverifier" src/
(no matches)

$ grep -A 5 "def verifiers" src/verification.py
def verifiers():
    """Imported here so a missing optional provider cannot break the module."""
    from .providers import contactout, deliverable, reoon
    return {"contactout": contactout, "deliverable": deliverable, "reoon": reoon}

$ grep -B 2 -A 3 "CALL_NAMES\|LEDGER_REASONS" src/verification.py
CALL_NAMES = {"contactout": "email-verifier",
              "deliverable": "deliverable-verify",
              "reoon": "reoon-verify"}

LEDGER_REASONS = {"contactout": None,
                  "deliverable": "verification_inconclusive",
                  "reoon": "verification_contradiction"}
```

**What this means:**
- `verification.verifiers()` returns only `{contactout, deliverable, reoon}` — CheapVerifier is absent
- `verification.CALL_NAMES` does not map CheapVerifier
- `verification.LEDGER_REASONS` does not map CheapVerifier
- `verification.call()` has no branch for `provider == "cheapverifier"`
- The waterfall's `record_step()` will accept CheapVerifier (the WaterfallViolation is gone), but no production code path will invoke it

**The result block acknowledges this:**
> "CheapVerifier is registered but NOT wired into any caller in src/. The module exists, the waterfall knows it, but no production code path calls verify_single() through the waterfall."

But it classifies this as a RISK rather than a blocker. **This is the whole task.** A waterfall entry with no caller is not "registered" — it is a dead entry that passes tests but does nothing in production.

**Reproduction command:**
```bash
$ py -3 -c "import sys; sys.path.insert(0, '.'); from src import verification; \
  print('verifiers:', list(verification.verifiers().keys()))"
verifiers: ['contactout', 'deliverable', 'reoon']
```

CheapVerifier is absent.

---

### Finding 3: Tests are not falsifiable — CONFIRMED

**Status:** NOT FALSIFIABLE

The tests prove:
1. CheapVerifier is in the EMAIL_VERIFICATION providers tuple ✓
2. `describe()` includes it ✓
3. ContactOut is before CheapVerifier ✓
4. `record_step()` does not raise WaterfallViolation ✓
5. `record_step()` writes a ledger row ✓

**What the tests do NOT prove:**
- That CheapVerifier is ever called in production
- That `verification.verify()` walks through CheapVerifier
- That a real email address would be verified by CheapVerifier

**How the tests could pass while the implementation is still wrong:**
The tests construct the waterfall step by hand and call `record_step()` directly. They never call `verification.verify()`, which is the production entry point. If you delete the CheapVerifier entry from `verification.verifiers()` (which does not exist, so there is nothing to delete), the tests still pass. The tests are testing the waterfall's registration, not the production caller chain.

**Mutation test:** Delete `waterfall.STAGES[waterfall.EMAIL_VERIFICATION]["providers"][1]` (the CheapVerifier entry). The tests fail. Now delete the CheapVerifier entry from a hypothetical `verification.verifiers()` — the tests still pass, because they never call `verification.verify()`. The tests are testing the wrong seam.

**What would make this falsifiable:**
- A test that calls `verification.verify(contact, live=False, rec=rec)` with a contact whose email would trigger CheapVerifier (e.g., ContactOut returned `verification_inconclusive`) and asserts that `cheapverifier.verify_single()` is called
- A test that asserts `verification.verifiers()` includes `"cheapverifier"`
- A test that walks the full waterfall and asserts the ledger includes a CheapVerifier step

---

### Finding 4: Scope drift — SIGNIFICANT

**Status:** SCOPE DRIFT CONFIRMED

The branch carries work from multiple tasks:
- TASK-285 (collision walk) — HEAD commit
- TASK-267 (LLM tiebreaker)
- TASK-358 (CheapVerifier) — the target of this review
- TASK-387 (provider event write-back)
- TASK-412 (suppression list audit)
- TASK-410 (GLM verdict for TASK-400)
- TASK-426 (bison staging)
- TASK-432 (GLM verdict for TASK-226)

**Total scope:** 39 files changed, 7,167 insertions(+), 223 deletions(-)

**TASK-358 specific changes:**
```bash
$ git log --oneline master..c8a62f4109f47eb5338f1ef334d68f44dcb989ef -- \
  src/providers/cheapverifier.py src/waterfall.py src/enrich.py \
  tests/test_cheapverifier_is_part_of_the_waterfall.py
5f6d83d78 TASK-358: add cheapverifier-verify to enrich COSTS and CALL_STAGE
b27c8452b TASK-358: CheapVerifier cherry-picked into the email_verification waterfall
```

**Cherry-pick scope:**
```bash
$ git diff master...c8a62f4109f47eb5338f1ef334d68f44dcb989ef --name-status | \
  grep -E "cheapverifier|waterfall\.py|enrich\.py"
A       src/providers/cheapverifier.py
M       src/enrich.py
M       src/waterfall.py
A       tests/cassettes/cheapverifier/auth_missing_key_401.json
A       tests/cassettes/cheapverifier/auth_wrong_key_403.json
A       tests/cassettes/cheapverifier/openapi_200.json
A       tests/cassettes/cheapverifier/single_missing_param_400.json
A       tests/cassettes/cheapverifier/stored_invalid_syntax_422.json
A       tests/cassettes/cheapverifier/stored_miss_404.json
A       tests/cassettes/cheapverifier/task_details_missing_404.json
A       tests/cassettes/cheapverifier/task_status_missing_404.json
A       tests/cassettes/cheapverifier/uploads_results_bad_status_422.json
A       tests/cassettes/cheapverifier/uploads_results_missing_404.json
A       tests/test_cheapverifier_is_part_of_the_waterfall.py
```

**What would need to be cherry-picked:**
- `src/providers/cheapverifier.py` (new file)
- `src/waterfall.py` (modifications)
- `src/enrich.py` (modifications)
- `tests/test_cheapverifier_is_part_of_the_waterfall.py` (new file)
- `tests/cassettes/cheapverifier/*` (10 new files)

**What would NOT be cherry-picked:**
- TASK-285 collision walk (docs/COLLISION-WALK-2026-09-25.md, scripts/collision_walk_report.py, tests/test_a_refused_domain_is_never_clear.py)
- TASK-267 LLM tiebreaker (scripts/stage_s3_llm_tiebreaker.py, tests/test_llm_tiebreaker.py)
- TASK-387 provider event write-back (tests/test_task387_provider_event_writeback.py)
- TASK-412 suppression list audit (docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md)
- TASK-410, TASK-432 GLM verdicts
- TASK-426 bison staging modifications

**Recommendation:** Cherry-pick only the TASK-358 files listed above. Do not merge the branch.

---

### Finding 5: Merging would not delete anything — VERIFIED

**Status:** SAFE TO MERGE (no deletions)

```bash
$ git diff master...c8a62f4109f47eb5338f1ef334d68f44dcb989ef --name-status | grep "^D"
D       docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
D       docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md
D       docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md
```

The deletions are task files moving from TODO to REVIEW (renamed/moved). No production code would be deleted. The merge is safe from a deletion standpoint.

---

### Finding 6: The result block's FINDINGS section is accurate — VERIFIED

**Status:** VERIFIED

The result block's FINDINGS section accurately describes the state:
1. Another worker (b27c8452) already completed the core task with a different design (CheapVerifier second, is_fallback=False) — VERIFIED
2. The remote's implementation was MISSING enrich.COSTS and enrich.CALL_STAGE entries — VERIFIED (commit 5f6d83d78 added them)
3. The remote placed CheapVerifier second with is_fallback=False — VERIFIED

The RISKS section accurately identifies the defect:
> "CheapVerifier is registered but NOT wired into any caller in src/. The module exists, the waterfall knows it, but no production code path calls verify_single() through the waterfall."

**However:** The result block classifies this as a RISK rather than a blocker. **This is the defect.** A waterfall entry with no caller is not "registered" — it is a dead entry.

---

## Disposition

### DISPOSITION: REWORK — DISCONNECTED

**Reason:** CheapVerifier is registered in the waterfall but has zero production callers. The module exists, the waterfall knows about it, the tests pass, but `src/verification.py` does not import it, does not list it in `verifiers()`, and does not invoke it. This is the exact defect documented in QWEN.md: "Existence is not function... a thing computed correctly that nothing downstream reads."

**What is owed:**
1. Add CheapVerifier to `src/verification.py`:
   - Import: `from .providers import contactout, deliverable, reoon, cheapverifier`
   - Add to `verifiers()`: `return {"contactout": contactout, "deliverable": deliverable, "reoon": reoon, "cheapverifier": cheapverifier}`
   - Add to `CALL_NAMES`: `"cheapverifier": "cheapverifier-verify"`
   - Add to `LEDGER_REASONS`: `"cheapverifier": "verification_contradiction"` (or whatever the policy dictates)
   - Add a branch in `call()` for `provider == "cheapverifier"` that invokes `cheapverifier.verify_single(email)`
2. Add a test that calls `verification.verify()` and asserts CheapVerifier is invoked
3. Re-run the full suite to ensure no regressions

**What is NOT owed:**
- Re-ordering the waterfall (ContactOut is correctly first)
- Re-registering in enrich.COSTS/CALL_STAGE (already done)
- Re-writing the module (already cherry-picked correctly)

---

## Recommendation

**REWORK**

Cherry-pick only the TASK-358 files (listed in Finding 4) to a clean branch. Add the missing wiring in `src/verification.py`. Add a test that proves the production caller chain is connected. Re-run the full suite. Then this is MERGE-ready.

**Do not merge the branch as-is.** The branch carries significant scope drift (TASK-285, TASK-267, TASK-387, TASK-412, TASK-410, TASK-426, TASK-432) and the CheapVerifier registration is disconnected from the production caller chain.

---

## Evidence

All evidence is in the worktree `glm-verify-task-358` at commit `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`.

**Reproduction commands:**
```bash
# Verify the waterfall order
py -3 -c "import sys; sys.path.insert(0, '.'); from src import waterfall as W; \
  d = W.describe(); provs = [p['provider'] for p in d[W.EMAIL_VERIFICATION]['providers']]; \
  print('email_verification order:', provs)"

# Verify the tests pass
py -3 -m unittest tests.test_cheapverifier_is_part_of_the_waterfall -v

# Verify CheapVerifier is NOT in the production caller chain
py -3 -c "import sys; sys.path.insert(0, '.'); from src import verification; \
  print('verifiers:', list(verification.verifiers().keys()))"

# Verify no imports of cheapverifier in src/
grep -rn "from.*cheapverifier\|import.*cheapverifier" src/
```

---

## Metadata

- **Review trigger:** TASK-497 (GLM independent verification)
- **Standing operator rule:** Every branch reaching REVIEW gets a GLM verdict dispatched against its EXACT head SHA immediately
- **Review contract:** GLM-REVIEW-PROTOCOL.md §5 (isolated worktree, exact SHA, read-only, cite evidence, distinguish static/runtime proof, mark unsupported claims)
- **Disposition contract:** GLM-REVIEW-PROTOCOL.md §6 (falsification over confirmation)
- **Reviewer model:** GLM (independent review layer)
- **Review date:** 2026-10-12
- **Artifact kind:** Code review (finding)
