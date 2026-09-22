# Merge request — the GLM review harness refuses a prompt with no source

**For the main session.** Branch `infra` at `006a8be8`, pushed to
`origin/infra`. Worktree `../resonate-infra`. Master untouched at `c75b4b60`.

Small, self-contained, and it closes PROBLEM-REGISTER **ISSUE-008** while
voiding one filed review document. Nothing in it touches `src/providers/`,
`config/.env`, a watch loop or `work/`.

---

## 1. THE DEFECT, AND IT ALREADY FIRED

`glm_review` built every prompt as:

    question.format(name=name, source=inspect.getsource(fn))

`str.format` ignores a keyword the template never mentions.
**`ATTRIBUTION_QUESTION` had no `{source}` placeholder**, so both of its calls
shipped the question text alone, and GLM was asked to review
`inbound._positively_not_ours` and `inbound.handle` having been shown neither.

It ran live on 2026-09-21 and the output was filed as
`docs/GLM-REVIEW-ATTRIBUTION-2026-09-21.md`.

**The receipt was already in that file.** Both calls:

    'prompt_tokens': 312
    'prompt_tokens': 312

Identical, for two different functions, because the prompt did not depend on
which function was under review. Every target whose template does carry its
source varies: 400, 752, 1,078, 1,823, 2,172.

The model reported it too, and was not read as reporting it:

> *"assertable without your code"* · *"I cannot construct a concrete drop
> **without the body of `_positively_not_ours`**"* · *"If you already do
> positive client-list matching, this finding is void — tell me which
> comparison you use."*

**Consequence for the register.** ISSUE-001's attribution path has NOT had an
adversarial second opinion. It is recorded as having had one.

---

## 2. THE FIX

`build_prompt(question, name, fn)` in **both** harnesses, same name, same
signature, same exception:

- Refuses with `PromptCarriesNoSource` when the **rendered prompt** does not
  contain the function's source. Checked against the rendered text rather than
  the template, because a placeholder that is present but mis-spelled passes a
  template check and still ships a sourceless prompt.
- Called **before `--live` is consulted**, so a broken template is a non-zero
  exit on a dry run — no credential, no network call, no charge. The previous
  one was found by paying for it twice.
- `ATTRIBUTION_QUESTION` gets the placeholder it was missing.

Both harnesses, because `glm_audit_safety.py` is the same shape and a guard in
one of two near-identical scripts is how the next sourceless review runs.

### ISSUE-008: the budget

`--max-tokens` default **6,000 → 16,000** in both, as `DEFAULT_MAX_TOKENS`.

ISSUE-008 records both targets returning `finish_reason='length'` with an
empty completion and offers "smaller review targets, **or** a raised output
budget". This is the second. `glm-5.3` spends most of its budget on REASONING
— 6,592 reasoning tokens of 7,266 completion on that same run — so the cap
limits the thinking that precedes the answer, not the answer. 16,000 is half
the adapter's `MAX_TOKENS_CAP` of 32,768.

**The adapter's own `DEFAULT_MAX_TOKENS = 1024` is NOT changed.** It lives in
`src/providers/glm.py`, which is the production session's file under the
three-session rule. Both harnesses always pass `max_tokens` explicitly, so
they never reach that default and the change was not needed. **If you want the
guard at the adapter instead of in the two harnesses, that is your call and
your file** — it is the stronger place for it, and it would cover any future
caller.

---

## 3. VERIFICATION

    tests/test_a_review_call_carries_its_source.py      11 tests, green

Written first and confirmed red for the intended reason before the fix.

Attacked, not just asserted. The exact pre-fix template was restored in
process and `main(["--target","attribution"])` re-run as a **dry run**:

    REFUSED on the dry-run path, before --live and before any call:
        the prompt for inbound._positively_not_ours does not contain its
        source ...

Dry-run character counts, after:

    attribution   inbound._positively_not_ours   2,015 chars
                  inbound.handle                 9,331 chars

Two different numbers where there were two identical ones.

The test build is deliberately derived from `_targets()` itself, so a target
added later is covered without anyone remembering to add it, and it asserts
the 312/312 symptom separately as a property — two functions in one target may
not render the same prompt.

---

## 4. WHAT YOU NEED TO DECIDE

1. **Merge it.** No production path, no provider write, no state change.
2. **Re-run `--target attribution --live`** to get the review that document
   was supposed to be. It is a real gap on ISSUE-001, not a formality. ~2
   calls.
3. **ISSUE-008 → FIXED** once merged, with the caveat that the empty-completion
   symptom is fixed by the budget and the *wasted* call was also caused by the
   missing source. Two causes, one symptom.
4. **The register wants a new row** for the sourceless review — it is the
   "cached value that had no way to notice it had gone stale" pattern arriving
   in a prompt template. Suggested text in section 5.
5. **Optional, yours:** move the guard into `src/providers/glm.py` so it covers
   every caller rather than the two harnesses.

---

## 5. SUGGESTED REGISTER ROW

```
### ISSUE-014 · A GLM review ran with no code in the prompt · MEDIUM · FIXED `006a8be8`

`ATTRIBUTION_QUESTION` carried no `{source}` placeholder and `str.format`
ignores a keyword the template never mentions, so the 2026-09-21 attribution
run sent the question text alone. Both calls report `prompt_tokens: 312` -
identical for two different functions - against 400-2,172 for every target
that does carry its source. The model said it could not answer without the
body and the output was filed as a review anyway.

- **Consequence** ISSUE-001's attribution path has NOT had a second opinion.
  `docs/GLM-REVIEW-ATTRIBUTION-2026-09-21.md` is marked VOID in place.
- **Fixed** `build_prompt` refuses when the RENDERED prompt lacks the source,
  on the dry-run path before `--live`. Both harnesses. 11 tests, verified by
  restoring the pre-fix template and confirming the refusal.
- **Not re-run yet.** The review itself is still owed.
```

---

## 6. ALSO IN THIS COMMIT, AND IT IS A DESIGN ONLY

`docs/STORE-SQLITE-DESIGN-2026-09-22.md` — the SQLite store design and its
task breakdown. **Nothing is wired and no behaviour changed.** It is in this
commit because it is a document, not because it is ready.

One number in it belongs to you now, because it corrects a measurement this
repository has been planning against:

> `queuejournal.py`'s headline table — 4,369.1 MB at 5,000 records — works out
> to **874 bytes per record**. The real queue today is **1,027 records,
> 19.41 MB, mean 19,819 bytes**. The profile was run on records **22.7x
> smaller than production's**, so every byte and wall-clock figure in that
> table is low by that factor.

At the measured mean, one pass over 20,000 records writes **1.48 TB**, and the
read is O(N) per checkpoint on top. The brief's "~31 KB per record" is also
corrected: 31 KB is inside the range (largest record is 162 KB) but the mean
is 19.8 KB, so every projection in the design is the conservative version.

It does not close TASK-226 (the journal offset index, work on
`qwen-worker-8-r28`). The journal stays the default until SQLite is proven in
shadow, so that task is not superseded yet.
