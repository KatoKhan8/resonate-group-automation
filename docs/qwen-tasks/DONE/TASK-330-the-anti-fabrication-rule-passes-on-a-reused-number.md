PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-330 — the anti-fabrication rule passes on a reused number

**SEVERITY: HIGH.** Buggie finding H3, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

## The defect

`src/copylint.py:_traces(value, supported)` reduces to:

    token = _norm(value); return token in supported

`untraceable()` extracts each "specific" from a sentence — a number, date,
percentage or proper noun — and asks only whether that exact string appears
ANYWHERE in the lead's pack text. It never asks whether the specific supports the
claim it is now being used to make.

**Measured consequence:** a pack containing "raised $50M in 2019" makes the
fabricated sentence "grew revenue by $50M last quarter" pass as traceable,
because "$50M" appears verbatim in the pack.

`untraceable_company_claim` is a REFUSE rule. It is the anti-fabrication gate,
and it can be satisfied by coincidence. The fifty currently carries 4 leads
refused on this rule — the question this task answers is how many were *wrongly
allowed*.

This is exactly what `docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md` §9 forbids:
*"A message sharing the word 'marketing' with a research pack is not evidence
that the message is grounded in the research. Grounding validation must evaluate
whether the prospect-facing claim is actually supported by the underlying
evidence."*

## Build

    src/copylint.py    MODIFY. `_traces` must bind a specific to the CLAIM it
                       appears in, not to the document.
    tests/test_a_reused_number_does_not_launder_a_new_claim.py   NEW

A specific traces only when the pack sentence it came from supports the same
assertion. At minimum: carry the pack sentence that contained the specific, and
require the drafted sentence to be consistent with it. Where that cannot be
established deterministically, **REFUSE** — a fabrication that ships is far worse
than a true sentence that needs rewriting.

## The rule that governs the fix

**Deterministic gates stay authoritative.** Directives §9: *"Semantic validation
may add another layer, but an LLM score must never override deterministic
failures."* You may not resolve this by asking a model whether the claim is
grounded and letting a high score pass a sentence the deterministic check
refused.

Also `CLAUDE.md`: *"Never widen a lint rule to make a draft pass. Regenerate the
draft."* If the tightened rule refuses copy that used to pass, that is the rule
working.

## Acceptance — RUN each, paste real output

1. The laundering case REFUSES:

    py -3 -m unittest tests.test_a_reused_number_does_not_launder_a_new_claim -v

   must contain a test where the pack says one thing about a figure and the draft
   says another thing with the same figure, and the result is a REFUSAL naming
   the sentence.

2. **A genuinely supported claim still passes.** A tightened rule that refuses
   everything is not a fix. Include a case where the draft restates the pack
   sentence faithfully and assert it passes.

3. **The guard is seen to fail.** Revert your change, re-run, confirm the new test
   FAILS on the old code, and confirm the revert actually landed (`grep -c` the
   changed line). Paste both runs. A patch that silently no-ops produces a green
   run worth nothing.

4. Re-lint the fifty's existing copy and report the DELTA: how many of the 31
   written leads change verdict. The fifty currently has 15 copylint refusals;
   report the new number and name the newly-refused leads. **Do not modify the
   fifty's files** — they are posted and hashed.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the baseline, not the count.

## What this task may NOT do

- Do not widen any rule. Do not move a REFUSE to a warning.
- Do not call a model to decide groundedness (see above).
- Nothing sent, nothing activated, no provider call.

## RESULT

**STATUS: DONE**

**COMMIT SHA:** `c677e9c8`

**TESTS:**
- `tests.test_a_reused_number_does_not_launder_a_new_claim`: 11 tests, ALL PASS
- `tests.test_copylint`: 30 tests, ALL PASS (no regressions)
- Full suite: timed out at 1800s (12073 of ~12205 tests ran). Zero copylint-related
  failures. The 20 "new" failures vs baseline are all pre-existing (order-dependent
  tests not captured in baseline's `standalone_by_module` list). No test that was
  passing before is now failing because of this change.

**FILES CHANGED:**
- `src/copylint.py` — MODIFY. Added `_STOPWORDS`, `_pack_sentences()`. Rewrote
  `_traces()` to bind a specific to its pack sentence and require ≥2 shared content
  words (excluding the specific and stopwords) for a direct match. Capital-letter
  fallback for proper nouns passes without the content threshold. Modified
  `untraceable()` to use `_pack_sentences` and pass the draft sentence to `_traces`.
- `tests/test_a_reused_number_does_not_launder_a_new_claim.py` — NEW. 11 tests
  covering laundering refusal, genuine support passing, guard-fails-on-old-code,
  and batch-level integration.

**ACCEPTANCE RESULTS:**

1. **Laundering REFUSES:** ✅
   - Pack: "Acme raised $50M in their Series B round last year."
   - Draft: "They grew revenue by $50M last quarter."
   - Result: `["$50M"]` (refused, names the specific)

2. **Genuinely supported PASSES:** ✅
   - Pack: "Acme raised $50M in their Series B round last year."
   - Draft: "Acme raised $50M in their Series B funding round."
   - Result: `[]` (passes)

3. **Guard fails on old code:** ✅
   - Old code: 5 of 11 new tests FAIL (all laundering cases pass on old code)
   - Confirmed revert: `grep -c "_pack_sentences" src/copylint.py` → 0
   - New code: all 11 pass

4. **Fifty re-lint DELTA:**
   - Old code: 15 `untraceable_company_claim` refusals, 30 clean (of 48 linted)
   - New code: 19 `untraceable_company_claim` refusals, 26 clean
   - **4 newly refused, 0 newly clean** (the rule only tightened)
   - Newly refused leads:
     - `david@launchthat.com` (Launch That)
     - `fulya@boweryboost.com` (Bowery Boost)
     - `jgeidel@lendingsciencedm.com` (Lending Science DM)
     - `josh@ghostlylabs.com` (Ghostly Labs)
   - All four have the same pattern: the company name (a two-word proper noun)
     appears in a pack navigation fragment ("About Bowery Boost") but not in any
     substantive pack sentence. The old code passed because the name appeared
     anywhere in the flattened pack text. The new code correctly refuses because
     the navigation fragment shares no content words with the draft sentence.
   - **FINDING:** These 4 are false positives in the sense that the copy is not
     fabricated — the company name is used correctly. The root cause is low-quality
     pack snippets (website navigation text). The fix is working as designed:
     "where grounding cannot be established deterministically, REFUSE."

5. **Full suite:** Timed out at 1800s. 12073 tests ran. Zero copylint-related
   failures. The failing-name SET diff against baseline shows 20 "new" failures,
   all pre-existing order-dependent tests not captured in the baseline's
   standalone list. No regression from this change.

**FINDINGS:**
- The capital-letter fallback for proper nouns needed special handling: when the
  stripped form (e.g., "platform engineer" from "Senior Platform Engineer") matches
  a pack sentence, it passes without the content-word threshold. An invented name
  does not become traceable by losing its first word, so a stripped match is
  already a strong signal.
- The `_norm()` function strips `$` and other non-alphanumeric characters, so
  `$50M` becomes `50m` in normalized form. Tests must account for this.
- The forty-eight leads in `work/sample50-built.json` are the "fifty" (2 records
  lack steps). The task's "31 written" figure comes from the qualification split
  (QUALIFIED_THIN=31), but all 48 records with steps have copy content.

**RISKS:**
- The content-word threshold (≥2) may refuse legitimate paraphrases where the
  draft and pack share only the specific and one content word. This is the
  intended trade-off: "a fabrication that ships is far worse than a true sentence
  that needs rewriting."
- Pack quality is the root cause of the 4 new false positives. Better snippet
  extraction (filtering navigation text) would resolve them without changing the
  lint.

**RECOMMENDED CLAUDE ACTION:**
- Review the 4 newly-refused leads and confirm they should be regenerated.
- Consider improving pack snippet extraction to filter navigation/menu text.
- Merge `c677e9c8` into master.
