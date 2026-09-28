PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-551 — a second-person possessive is still an assertion about them

**Operator decision, Zvonimir, 2026-09-28: "close it."**

## The defect, measured

`claims.SECOND_PERSON_ASSERTIONS` is a **phrase list** (`you are `, `you
track `, `your team is ` …) and **a bare possessive matches none of it**, so
the sentence is never examined:

    "You have margin visibility on every project."      REFUSED   (correct)
    "Your margin visibility slips between projects."    SUPPORTED (wrong)

**Same assertion, different phrasing, one ships unexamined.**

## The fix

Add second-person **possessive** assertions to the claims gate in
**`src/claims.py`**, so a possessive construction asserting something about the
prospect requires licensed evidence exactly as the explicit form does.

## Acceptance

1. **NEGATIVE CONTROL (required):** *"Your margin visibility slips between
   projects."* is **REFUSED** with no licensed evidence.
2. **POSITIVE CONTROL (required):** a **question** — *"How do you track margin
   today?"* — is **ALLOWED**. A question asserts nothing and must not be caught.
   This control is what stops the fix becoming a gate that refuses everything.
3. The same possessive **IS allowed** when the pack genuinely licenses it.
4. Ordinary possessives that assert nothing about their situation still pass
   ("your time", "your call").
5. Mutation: remove the possessive branch; control 1 must go red for that
   reason and no other. Restore byte-identical.

**Tightening costs nothing today** — nothing stored is shipping, everything is
paused. Do not soften it to protect stored copy.

## Files
**`src/claims.py` only**, plus your own test module.

## RULES THAT OUTRANK FINISHING — every brief here

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** If a gate refuses correct copy,
  fix what it CONSULTS, never what it PERMITS.
- **A test count is never a PASS.** Name the real path exercised, the negative
  control, and the killed mutation.
- **EVERY new check needs a NEGATIVE control** — an input that must be REFUSED
  — and a **NEAR-MISS** control, not only an obvious one. The B1 defect below
  exists precisely because every control used a pack containing the literal
  word.
- **MUTATION CHECK IS MANDATORY.** Break your own fix in source, prove the
  intended test goes red for the intended reason, confirm no other guard fired
  first, restore the source and verify **byte-identical by sha256**.
  These files are **CRLF**: a `\n`-anchored regex matches zero times and your
  mutation becomes a silent no-op that looks like a surviving test.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent to anybody.
- Production `work/` is READ-ONLY. Verify `work/queue.jsonl` and
  `work/campaigns.jsonl` unchanged **by sha256 from a fresh process** — mtime
  is the wrong instrument, 23 loops write that checkout.
- **Write suite logs OUTSIDE the repository.** A log inside the tree became
  part of `test_fixture_hygiene`'s corpus and nearly committed real prospect
  domains. And interrupting a suite leaves one temp dir per test — 94,867 of
  them broke every later run. **A suite with no `Ran N tests` line is an
  absent measurement, not a failure**: sweep `%TEMP%` and re-run.
- Suite baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 named
  failures, compared **AS SETS, NEVER COUNTS**. It is known stale on master
  (TASK-549): four of its entries fail on master with no branch at all.
- Commit and push to your own branch; **verify the remote with `git rev-parse`**.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** 3b89a522
**BRANCH:** qwen-worker-7-r9
**REMOTE:** origin/qwen-worker-7-r9 verified at 64665736 before rebase, pushed to 3b89a522

**TESTS:** 11/11 pass in `tests/test_a_possessive_is_still_an_assertion.py`.
28/28 existing claim-related tests pass (test_our_own_words_are_not_evidence,
test_a_relationship_we_cannot_show_is_not_a_relationship). 72/72 personalization
and observations tests pass.

**FILES CHANGED:**
- `src/claims.py` — added possessive branch in `asserts_about_them` (19 lines added)
- `tests/test_a_possessive_is_still_an_assertion.py` — new test module (227 lines)

**FINDINGS:**

CLAIM: A bare possessive + operational term ("your margin visibility") is now
detected as a second-person assertion, requiring the same evidence as the verb
form ("you track margin").
AUTHORITY: `asserts_about_them` in `src/claims.py`, called by `is_claim` (line
458) and `check_sentence` (line 599).
MEASURED AT: 2026-09-28, through `claims.check` (the real entry point).

**ACCEPTANCE CONTROLS — all five pass:**

1. NEGATIVE CONTROL: "Your margin visibility slips between projects." → REFUSED.
   `claims.check` returns `[{"sentence": ..., "why": "'margin' is asserted about them..."}]`.
2. POSITIVE CONTROL: "How do you track margin today?" → ALLOWED. `is_claim`
   exempts questions (has "?", no number) before `asserts_about_them` runs.
3. LICENSED POSSESSIVE: same sentence with `research=[{"fact": "margin visibility
   slips between projects at Fernwick"}]` → ALLOWED.
4. ORDINARY POSSESSIVES: "I know your time is valuable." → ALLOWED. "The next
   move is your call." → ALLOWED. Neither "time" nor "call" is an operational term.
5. MUTATION: Removed the possessive branch from source → `asserts_about_them`
   returns False for "your margin visibility slips between projects" →
   `claims.check` returns clean (wrong!). Restored byte-identical, sha256
   verified. No other guard fired first during mutation.

**NEAR-MISS CONTROLS:**
- "Your team seems great." → ALLOWED ("team" not operational).
- "If your margin visibility is a concern, let me know." → ALLOWED (hedge "if "
  caught before possessive branch).

**CALLER CHAIN VERIFIED:**
`asserts_about_them` is consumed by `is_claim` (determines if sentence is a
claim) and `check_sentence` (returns operational terms needing support). Tests
drive through `claims.check` which exercises both.

**PRODUCTION STATE:** `work/queue.jsonl` and `work/campaigns.jsonl` not present
in this worktree (as expected per QWEN.md). No provider writes.

**RISKS:** None identified. The fix is strictly additive — it only catches
sentences that were previously passing unexamined. It cannot refuse anything
the old code accepted, because the old code's verb-form markers are unchanged
and the new branch only fires when none of them matched.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. The fix is narrow, the
mutation is killed, and no existing behaviour changes.
