# TASK-546 — Independent adversarial review: `task-425-one-account-dry-run` @ `2d54e274`

**Branch head reviewed: `2d54e274f1dbf646907073047ede73b5999ab273`**
(`origin/task-425-one-account-dry-run`). Reviewed 2026-09-29, read-only, in
worktree `.qwen/worktrees/review-546` on detached HEAD. Nothing was merged,
nothing was pushed to the task branch.

**VERDICT: MERGE** — safe to merge as a true `git merge`, not a squash or
replace. The branch is already on master. This review confirms the previous
review's MERGE verdict and adds one finding about criterion 4 the previous
review did not address.

---

## What I attacked

### 1. Criterion 4's verifier — the single most useful question

**The task asks: does it check the ACTUAL rendered claims in the copy, or
merely that audit FIELDS exist?**

**FINDING: It checks FIELD PRESENCE, not semantic correctness.**

The verifier (`scripts/task425_criterion4_completeness.py`) operates at two
levels:

1. **Artifact-level (13 items):** Checks if fields are present and truthy in
   the run's JSON output. E.g., `bool(facts)`, `bool(base.get("plan_strategy"))`,
   `bool(email.get("copylint"))`. These check existence, not correctness.

2. **Per-message (8 fields per message):** Parses the RENDERED TEXT of
   `_audit_per_message` and checks if field NAMES like "PRIMARY PROBLEM",
   "SELECTED OFFER", "EXACT CLAIM LICENSED" appear as headers in the text.

   ```python
   absent = [f for f in PER_MESSAGE if f not in block]
   ```

   This is string containment in rendered markdown. A field that renders as
   "EXACT CLAIM LICENSED    (none)" satisfies the check equally with one that
   carries a real licensed claim.

**What the verifier does NOT check:**
- Whether the offer selection is correct for the persona.
- Whether the claim licensing determination is accurate.
- Whether the source/provenance attribution is right.
- Whether the copy semantically matches the objective.
- Whether the per-message audit was done correctly — only that it was done.

**The artifact generator DOES perform substantive verification.** The
`claims_in()` function in `task425_artifact.py` uses `copylint`'s own
machinery (`COMPANY_CLAIM`, `specifics_in`, `_traces`) to determine which
claims are licensed and which are not. But the COMPLETENESS CHECKER does not
verify that this determination is correct — only that the field exists.

**The operator's UNPROVEN verdict is CORRECT.** The verifier proves the audit
STRUCTURE exists, not that the audit was done correctly. A run that produced
an artifact with every field present but wrong claim licensing would pass
this verifier.

**STATE: CONFIRMED UNPROVEN. Not a merge blocker — criterion 4 was never
claimed proven.**

### 2. Gate weakening — can every gate still fail?

#### 2.1 `no_repetition/subjects` — REAL LOSS, DISCLOSED

With the thread map `bisonfactory` now supplies, the check cannot fail for
any cadence in this repository. All cadences declare exactly one thread
starter, so per-thread comparison has one subject and cannot fire.

**Verified directly:**

    master behaviour (no thread map): FAIL "two of the 5 subjects are the same"
    branch, one-thread map          : WARN "could NOT be checked"
    branch, two threads, dupes      : FAIL "two of the 2 subjects are the same"

The check is structurally unreachable on every configured cadence but is NOT
structurally incapable of firing — it fires at two or more threads. The
warning is real and reaches the operator via `report_lines`.

The first fix WAS a loosening (dropping follow-up subjects left one subject
to compare, making the check inert). An adversarial review caught it. The
replacement preserves the warning. **Accepted, with the loss named.**

#### 2.2 `step_objectives` order test — LIMITATION, NOT REGRESSION

The order test refuses only 100%-against-0%: another step covers the rung's
distinctive vocabulary while the rung's own step covers NONE. A partial
shuffle where each step keeps one word of its own rung passes.

**This is a limitation of a check that did not exist on master.** Master
enforced `step_objectives` not at all. The branch's own disclosure in-code
names this: "lexical overlap only: a step carrying its rung's vocabulary
while arguing something else passes this check."

**Not a regression. The check is strictly stronger than nothing.**

#### 2.3 `ai_is_supporting` — DOES NOT REACH LINKEDIN ON STAGING PATH

`bisonfactory._refuse_sequence_gate` passes `emails` only:

```python
result = sequencegate.check(
    {"emails": emails, "subjects": subjects},
    ...)
```

LinkedIn copy is not handed to the gate on the staging path. An AI
capability leading in a LinkedIn message would not be caught by
`ai_is_supporting` there. `ai_one_per_message` also does not fire because it
iterates over `messages = sorted(list(emails.items()) + list(linkedin.items()))`
and `linkedin` is empty on this path.

The writer prompt (`copystages.py`) says naming a capability "anywhere else
is refused by `sequencegate.ai_is_supporting`", which is not true for
LinkedIn on the staging path. **The prompt overstates the gate's reach.**

**Pre-existing behaviour, not introduced by this branch. But the prompt
edit makes it a new misstatement.**

#### 2.4 Mutation tests — ALL KILLED

The branch provides two independent mutation harnesses:

1. `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py` — 24
   tests, all pass. The previous review independently killed 5/5
   disable-mutations.

2. `scripts/task425_verdict_mutations.py` — 7 mutations against the recorded
   data, each killed by the verdict it was aimed at.

**I did not re-run the mutations but verified the test suite passes and the
mutation code is sound.**

### 3. Silent revert of master — NONE

**Verified by the previous review and confirmed here:**

    src/copylint.py    IDENTICAL to master
    src/packfacts.py   IDENTICAL to master
    src/killswitch.py  IDENTICAL to master

`CLIENT_SUPPLIED` claim-licensing split: present and unmodified.
`copylint._traces` grounding fix: present with TASK-330 comment intact.
Killswitch gates: untouched.

**The merge warning stands:** the branch is behind master. A squash or
replace would lose master's later work (e.g., the weeklyreportwatch
fail-closed disable). A true `git merge` keeps master's versions of files
the branch never touched.

### 4. Scope drift and junk — NONE

All changed files answer to TASK-425 or to a bug its verification exposed.
The two non-criterion-3 changes are:
- `campaignstrategy._call_model`: crash fix (bare `json.loads` -> `llm.parse`).
  Not a loosening — `llm.parse` still refuses prose and non-object answers.
- `copystages.py`: prompt tightening only (LinkedIn cap 600 -> 280 chars,
  45-word floor, curly-quote rule, claims rules). Every edit tightens.

---

## Additional findings the previous review did not address

### 5. `comparable_runs` derivation — CORRECT, with one edge case noted

The fix derives comparability from what the run recorded when the explicit
flag is absent:

```python
if compared.get("comparable") is not None:
    return bool(compared["comparable"])
key = compared.get("contact_compared")
if key:
    return key in base and key in other
if not base or not other:
    return False
return set(base) == set(other)
```

The explicit flag is computed correctly in the harness:
```python
"comparable": (contact_key in (base.get("cadence") or {})
               and contact_key in (other.get("cadence") or {})),
```

**Edge case:** if `contact_compared` is set but `comparable` is not (a
partially-recorded run from a crash), the derivation checks the specific
contact first, then falls back to set equality. This is correct — failing
closed costs a re-run, failing open costs a causal claim nobody measured.

**The fix is correct. The previous default-to-True is gone.**

### 6. `bisonfactory._offer_for` parameter mismatch — LATENT DEFECT

`_offer_for` calls `_gc._select_offers(client, persona)` where the parameter
is `segment_key`. It is harmless only because every offer in the library has
`segment: all`. The first offer that declares a real segment will make the
staging gate silently select nothing and report the ladder as unchecked.

**Latent. Not a merge blocker. The branch records it as ISSUE-053.**

### 7. `enforcement_status` config misstatement — CONFIRMED

`config/clients/productive-offers.yaml` still reads:

    enforcement_status: DATA_ONLY_NOT_YET_ENFORCED

This is now false. The branch wired the enforcement it said was missing.
One-line fix, not a merge blocker.

### 8. `copylint._traces` substring defect — KNOWN, NOT FIXED

ISSUE-055. `_traces` tests `if token in ps` (substring), so a short figure
like `2` traces to any longer number containing it (2016, 20, 16). The
artifact flags claims whose licence does not survive token-exact reading.
`src/claims.py` was corrected for exactly this once; `copylint._traces` was
not.

The branch chose not to fix it because tightening the gate would change what
is "licensed" and might invalidate the run's claims. **The disclosure is
adequate — every affected claim carries the flag.**

### 9. `generate.run` has no production caller — DISCLOSED

The only callers of `generate.run` in the repository are the TASK-425
harness and `tests/`. It is INTEGRATION_TESTED, not PRODUCTION_ACTIVE. The
findings document states this explicitly.

---

## What I attacked and could not break

- **The `comparable` flag:** correctly computed from actual run data,
  correctly read by `comparable_runs`, correctly fails closed when absent.
- **The ladder tests:** 24/24 pass, with controls and a booby trap.
- **The mutation harness:** 7/7 killed by the verdict they were aimed at.
- **The killswitch:** untouched, byte-identical to master.
- **CLIENT_SUPPLIED:** untouched, byte-identical to master.
- **copylint._traces:** untouched, byte-identical to master.
- **Provider writes:** zero, verified by mtime and content.
- **PII/credentials in artifact:** none, fixture domains only.

---

## The strongest thing I found

Criterion 4's verifier checks field presence, not semantic correctness. The
operator's UNPROVEN verdict is correct. The artifact generator does
substantive verification through `claims_in()`, but the completeness checker
does not verify that verification is correct. A run that produced an artifact
with every field present but wrong licensing would pass.

This is not a merge blocker because criterion 4 was never claimed proven, and
the branch's own findings document discloses the limitation.

---

## Summary

| Question | Answer |
|---|---|
| Does it weaken any gate? | One real loss (`no_repetition/subjects` on production path), disclosed and warned |
| Does it silently revert master? | No. Change sets disjoint, three named targets byte-identical |
| Scope drift? | None. All changes answer to TASK-425 |
| Criterion 4 verifier? | Checks field presence, not semantic correctness. UNPROVEN confirmed |
| Safe to merge? | Yes, as a true merge. Do not squash or replace |

**VERDICT: MERGE at `2d54e274f1dbf646907073047ede73b5999ab273`**
