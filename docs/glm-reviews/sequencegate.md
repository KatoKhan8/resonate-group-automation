# GLM adversarial review: sequencegate

_2026-09-26, file `src/sequencegate.py`_

**1. BYPASS**

Three concrete paths, strongest first:

- **Qualification is exact-match tuple membership.** Line ~97: `if qualification in ("UNQUALIFIED", "INSUFFICIENT")`. This is `==` against two strings, not substring. The codebase's own sentinel `INSUFFICIENT_DATA` does not match `"INSUFFICIENT"`, and the default `qualification=None` doesn't either. Call path: `check(seq, facts=..., qualification="INSUFFICIENT_DATA")` → the qualified check never fires → an unqualified lead ships. The evaluator that "returned INSUFFICIENT_DATA forever" is precisely the upstream whose value sails through here.
- **Vacuous pass on empty input.** Lines ~82–84 filter falsy values (`if v`); no check requires any content to exist. `check({})` returns `passed: True` with zero failures. Same for `facts=[]`: line ~144 `if facts and not (...)` skips `reason_for_outreach` entirely — and given this codebase's history of research facts never being wired through, the no-facts call path is the *likely* one, not an edge case.
- **The founding failure defeats the founding check.** `followup_adds_value` (line ~155) is bag-of-words overlap at 0.45. "Your margins are thin on fixed-scope work" vs "profit on flat-fee projects is squeezed": content-word intersection is empty → 0.0 → passes. Five phrasings of one argument — the exact 2026-09-25 failure in the docstring — is invisible to lexical overlap. Worse, `_content_words` (line ~56, `[a-z][a-z'-]{3,}`) drops all tokens under 4 chars, so `CRM`, `PPC`, `ads`, `SEO` never count toward repetition.
- Bonus: batch check (line ~193) `len(distinct) == 1` is case-sensitive on exact strings — one lead tagged `"Profitability"` among nineteen `"profitability"` → distinct=2 → passes. And `batch_capabilities=None` (the default) disables it outright.

**2. WHO READS THIS OUTPUT?**

Nothing in this file shows a consumer — `copylint` is imported *by* this module; nothing imports the result. Four reader/writer gaps visible from here:

- The batch check (lines ~191–194), commented "the most important one," requires the caller to hold the entire batch's capabilities. If sequences are generated and gated per-lead — the natural shape, since `check` takes one sequence — **no caller can ever pass `batch_capabilities`**, and the Stage D defaulting failure has no reader. Third instance of the pattern.
- Key mismatch inside the same function: check 2 reads `f.get("quote") or f.get("text")` (line ~106); check 5 reads only `f.get("text")` (line ~145). A producer writing `quote` makes check 5 fail every em1 (empty fact-text join → empty intersection → fail); a producer writing `text` only feeds copylint `snippet: None`. Whichever key the writer uses, one check reads a field that isn't written.
- `warnings` and the `checks` list: if the consumer branches only on `passed` (it's a gate), every warn-level check — hypothesis hedge, capability naming, word-count band, company merge-tell — is computed and consumed by no one.
- Line ~181 reads `sequence.get("company")`. If the writer keys it `company_name`, the merge-tell check never runs. Verify the writer's key.

**3. A TEST THAT CANNOT FAIL**

There are no tests in this file at all — a money-facing gate with zero executable verification is itself the finding. And the tautology traps are pre-built: `checks` in the return (line ~203) is a hardcoded literal, so any test asserting it compares a constant to a constant; `report_lines` on a passing result asserts the "PASSED" string it just formatted. Any test calling `check({})` and asserting `passed is True` is green because the gate is vacuous on empty input (see Q1), not because it is correct.
