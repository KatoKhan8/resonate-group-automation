# GLM branch verification: TASK-990

Branch: `task-removal-union-2026-10-12`
Date: 2026-10-11T23:31:58.474753+00:00
Model: glm-5.3
Duration: 163.036s
Usage: {'prompt_tokens': 11711, 'completion_tokens': 13719, 'total_tokens': 25430, 'reasoning_tokens': 12618, 'cached_tokens': 0}

## Verdict: FAIL

**the mandated 559-row before/after, positives-unchanged measurement, name-set baseline diff and mutation controls were never run, and unmeasured inputs (footer "unsubscribe from this list", "stop spam filters", "no further emails needed") now preempt POSITIVE/OUT_OF_OFFICE by construction.**

## GLM spend

This call: 1 ledger rows, 26635 micro-USD

## Changed files (2)

- `src/replies.py`
- `tests/test_a_removal_request_is_decided_first.py`

## Diff stat

```
 src/replies.py                                   | 287 +++++++++++++++--
 tests/test_a_removal_request_is_decided_first.py | 372 +++++++++++++++++++++++
 2 files changed, 642 insertions(+), 17 deletions(-)

```

## Acceptance output

```
NOTHING WAS RUN. This task declares no runnable acceptance commands, so there is no evidence here that the branch does what it claims. Treat question 2 as unanswerable and do not return PASS on the strength of the diff alone.

The task's acceptance criteria, stated as prose rather than as commands, are below. Judge the diff AGAINST THESE - that is what the branch promised:

- Classify all 559 real replies before and after. Report moved-in and moved-out
  counts. **Moved-out must be 0 for the bare one-word forms.**
- Precision must not move in the expensive direction: a genuine positive reply
  silently becoming a removal is a suppressed buying signal. Assert the positives
  are unchanged.
- Tests covering every one of the 11 phrases AND every bare one-word form.
- Negative controls: break each pattern group deliberately and show the intended
  tests fail for the intended reason.
- Existing classifier tests: a name-set diff against master, zero NEW failing
  names. A count is not a baseline; the baseline is the named list.
- No prospect address may appear in any test, fixture, doc or commit message.

(no acceptance commands extracted from task file)
```

## GLM response

## 1. Production caller

**YES.** `removal_request` is called from `classify_rules` (src/replies.py, hunk @@ -1246,25 +1505,19: `removal = removal_request(text); if removal: return removal`), and `classify_rules` is on `classify`'s path — proven by the passing tests that go through `replies.classify(text, model=None)` and receive rule verdicts (e.g. `test_the_row_that_was_announced_as_a_buying_signal`). Not dead code. Minor cost: `removal_request` re-runs `normalise(text)` that `classify_rules` already computed — 2× normalisation on every classified reply.

## 2. Can the acceptance check fail?

**As delivered, no — it is vacuous.** "NOTHING WAS RUN." The prose criteria demand a 559-row before/after run, a positives-unchanged measurement, a name-set diff against master, and mutation negative controls. None exists as a command or an artifact. The docstring claim "Measured over all 559 rows - 12 positives before, 12 after" (tests/…, class `PrecisionDidNotMove`) is a number with no run behind it.

If the check *were* run, nameable defeats — all in the expensive direction, and all invisible to the 4 hand-picked warm fixtures in `test_a_warm_reply_is_still_positive`:

- **Footer/quote defeat.** Pattern 1 (src/replies.py @@ +205) needs no pronoun: `\b(?:remove|…|unsubscribe)\s+(?:me|us|…)?\s*(?:from|off)\s+…lists?…`. Input: `"Sounds great, Thursday works. You can unsubscribe from our mailing list at any time."` → matches `unsubscribe from our mailing list` ("our" determiner, "mailing" modifier, "list" noun) → `removal_request` returns before any rule → **UNSUBSCRIBE 0.95**, was POSITIVE. The module's own comments confirm trailing footer text survives `normalise` ("a signature block collapsed onto the same normalised string", pattern-3 note), so quoted original footers are in scope. Same input class defeats `test_an_out_of_office_is_untouched`: `"I'm out of office until Monday. To unsubscribe from this list click here."` was OUT_OF_OFFICE, now UNSUBSCRIBE — the test's fixture carries no footer, so it passes while the regression exists. Note also this silently reorders whatever RULES placed above UNSUBSCRIBE (OUT_OF_OFFICE/AUTOMED placement is not shown and the branch overrides it by construction).
- **`\bstop\b[^.!?\n]{0,40}?\bspam`** fires on `"How do we stop spam filters blocking your invoices?"` — a prospect asking about their own mail problem → UNSUBSCRIBE 0.95.
- **`\bno\s+(?:further|more)\s+e?-?mails?\b`** fires on `"No further emails needed — just send the contract."` (warm) → UNSUBSCRIBE.

The bare-one-word moved-out=0 criterion is structurally plausible (all 7 master patterns retained; covered by tests), but unmeasured like the rest.

## 3. Do the numbers reconcile?

- **Reconcile:** BARE tuple = 7 master + 4 branch = 11 ✓ (diff shows 4 additions to a 7-pattern tuple; test asserts 11). `THE_ELEVEN` has 11 entries ✓. Test count 28 = 5+3+5+5+7+3 ✓ matches "Ran 28 tests".
- **Do not reconcile:** "12 positives before, 12 after over 559 rows" — no script, no data, no run; assertion only. "Fixed 13 / broke 7" and "eleven rows came back unknown 0.0" — comment-only, no artifact. "The seven were remove/Remove/REMOVE/unsub/Unsub" — 5 distinct strings for 7 rows; holds only if two forms repeat in the corpus; unverifiable.
- Deleted `first_line = _first_content_line(text)` in `classify_rules`: if any code below the shown hunk still referenced it, that's a NameError — the passing `classify` tests argue it was a dead assignment, but the hunk context doesn't prove it.

## Also checked

- Both changed files answer to TASK-990: src/replies.py (patterns + precedence) and the test file. Yes.
- No scratch files (*.txt/*.err/*.out) at repo root; changed-files list contains only the two files. No prospect address appears in tests/docstrings ("Some Company", `example.invalid`, `+44 000 000 0000` only).

VERDICT: FAIL - the mandated 559-row before/after, positives-unchanged measurement, name-set baseline diff and mutation controls were never run, and unmeasured inputs (footer "unsubscribe from this list", "stop spam filters", "no further emails needed") now preempt POSITIVE/OUT_OF_OFFICE by construction.
