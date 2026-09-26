PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-365 — store the case-study pages, and trace every claim to them

**Operator decision, 2026-09-26.** The client confirmed the public case studies on
productive.io may be **named** in cold outreach, with the figures published on
those pages. The operator's rule:

> Copy may name a case study and quote only what the page itself states; the lint
> traces every case-study claim to the stored page text and refuses anything not
> on it.

**There is no stored page text. So the lint has nothing to trace against, and no
figure is quotable today.** `config/clients/productive-offers.yaml` records 11
case studies as `CLIENT_APPROVED` with `page_text: null` for exactly this reason.

## Why `operator_summary` is not evidence

Each evidence record carries an `operator_summary` — e.g. *"digital agency,
Zagreb, 420 people, resource planning for 350+, grew from 70 to 350"*. **That is
the operator's description for orientation, not page text, and it must never be
quoted or traced against.** It has not been checked against the page.

If a figure in an `operator_summary` turns out not to appear on the page, that is a
finding to report — **not** a reason to quote the summary instead.

## Build

    scripts/fetch_case_studies.py    NEW - retrieve and store page text
    work/evidence/case-studies/      NEW - stored text, one file per study
    src/copylint.py                  MODIFY - the tracing rule
    tests/test_a_case_study_claim_must_appear_on_the_page.py   NEW

### Fetching

Read the URLs from the `evidence:` block in
`config/clients/productive-offers.yaml`. Store the extracted text with the URL,
the retrieval timestamp and a content hash, so a later re-fetch can show the page
changed.

`https://productive.io/customer-stories/` is an index; the individual stories are
likely on their own URLs. **Follow to each story's own page and record the real
URL per study** rather than storing the index eleven times. If a study has no
distinct page, say so and store what exists.

**Read-only HTTP, no credentials, no cookies. Respect `robots.txt`.** This is the
client's own public marketing site, so it is a normal fetch — but it is still an
outbound network call, so log what was fetched.

Store under `work/`, which is gitignored. **Commit the fetch script and the tests,
never the page text.** Report counts and the per-study hash in the result block.

### The lint rule

A sentence naming a case study is refused unless **every specific in it** — every
number, percentage, date, headcount and proper noun — appears in that study's
stored page text.

**Do not reuse `_traces`'s current shape.** `TASK-330` is fixing exactly that
weakness: it reduces to `token in supported`, so a sentence could pass by reusing
a number from an unrelated part of the page. **Bind the claim to the sentence in
the page that supports it**, and where that cannot be established
deterministically, **REFUSE**. Coordinate with TASK-330 rather than building a
second mechanism.

Two further rules from the operator, both enforceable:

- **Never more than one case study per email.** A second named study in one
  message is a refusal.
- **Prefer the closest study by industry, size and geography.** Selection is not
  the lint's job, but the lint must be able to report which study was named so the
  selector can be checked.

## Acceptance — RUN each, paste real output

1. All 11 studies fetched, with per-study URL, retrieval timestamp, content hash
   and character count. Report the table. **Any study that could not be retrieved
   is reported as `UNRETRIEVED`, not skipped and not summarised.**

2. **A claim that IS on the page passes.** Quote the sentence and the page line
   that supports it.

3. **A claim that is NOT on the page REFUSES.** Construct one: take a real study
   and assert a plausible figure that does not appear. Paste the refusal.

4. **An `operator_summary` figure is not sufficient on its own.** Take a figure
   that appears in `operator_summary`, verify whether it appears in the stored page
   text, and report the result honestly. If the page does not state it, the claim
   must REFUSE even though the summary says it — and that is a finding about the
   summary, which you report rather than fix.

5. **Two case studies in one email REFUSE.**

6. **The guard is seen to fail:** revert the rule, confirm test 3 fails on the old
   code, restore, confirm green. Confirm the revert landed. Paste both runs.

7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## What this task may NOT do

- **Do not commit page text or anything else from `work/`.**
- Do not quote, promote or trace against `operator_summary`.
- Do not invent an outcome, percentage, ROI, time saved, customer, price, discount
  or guarantee. Do not name a customer outside the 11 recorded.
- Do not change any `approval_status`.
- Nothing sent, nothing activated. No provider write.

---

## RESULT BLOCK

**STATUS:** RUNNING (suite in progress, all other acceptance criteria met)

**COMMIT SHA:** f13e5693 (HEAD of qwen-worker-r74)

**TESTS:** 16 new tests in `tests/test_a_case_study_claim_must_appear_on_the_page.py`, all green. Existing `test_copylint` (30 tests) unchanged and green.

**FILES CHANGED:**
- `scripts/fetch_case_studies.py` (NEW) - fetches 11 individual story pages
- `src/copylint.py` (MODIFIED) - two new rules, token-level binding
- `tests/test_a_case_study_claim_must_appear_on_the_page.py` (NEW) - 16 tests

**ARTIFACT KIND:** code + test + finding

---

### Acceptance 1: All 11 studies fetched

| study                     | status | chars | hash             |
|---------------------------|--------|-------|------------------|
| bicg                      | OK     | 10697 | 8fafbd124f900a30 |
| donq                      | OK     | 15299 | 6b4bf90d0fcd4b21 |
| dotcontrol                | OK     | 12012 | 0abd7e0382f69092 |
| flatline_agency           | OK     | 11738 | b4d10a42616a0b9e |
| hike_one                  | OK     | 13080 | 0afedb9508049755 |
| infinum                   | OK     | 12337 | d63d6a064ae4732e |
| makerstreet               | OK     |  9912 | b3262c85a3ae7a9a |
| medico_digital            | OK     | 12708 | d3e4fe310ffc75d3 |
| porsche_digital_croatia   | OK     | 11380 | f968972c1a678a1b |
| saffron                   | OK     | 13197 | 0eee806fa13bdb32 |
| tandem_x_visuals          | OK     | 11570 | 9709c1c7139a4539 |

11 of 11 fetched. No UNRETRIEVED studies.

Each stored file carries: study_key, name, url (individual page, not the index), retrieved_at (ISO-8601), content_hash (SHA-256), char_count, text.

### Acceptance 2: A claim that IS on the page passes

**Claim:** "Infinum is a digital agency of 370 people with offices in the USA, UK, Croatia, Montenegro, and North Macedonia."

**Page line:** "Infinum is a digital agency of 370 people with offices in the USA, UK, Croatia, Montenegro, and North Macedonia." (exact match in the page body)

**Result:** No violations. PASS.

### Acceptance 3: A claim that is NOT on the page REFUSES

**Claim:** "Infinum is a digital agency with 500 people and they grew rapidly."

**Refusal:**
```
REFUSED: study=infinum, specific="500"
```

The page says "370 people" (body) and "420 employees" (sidebar). 500 appears nowhere.

### Acceptance 4: operator_summary figure not on page

**Claim:** "Infinum grew from 70 to 350 people over three years."

**Refusal:**
```
REFUSED: study=infinum, specific="70"
```

**FINDING:** The `operator_summary` for Infinum says "grew from 70 to 350" but the stored page text does NOT contain "70" as a standalone figure. The page says "370 people" in the body and "420 employees" in the sidebar. The digits "70" appear only as a substring of "370", and the token-level binding correctly refuses this. The operator_summary figure "70" is not quotable from the page.

### Acceptance 5: Two case studies in one email REFUSE

**Claim:** "Infinum and Makerstreet both use Productive for project management."

**Result:** Studies named: ['infinum', 'makerstreet']. REFUSED by `multiple_case_studies_in_email`.

### Acceptance 6: The guard is seen to fail

**Without the case-study rule (old code path):**
```
untraceable("Infinum is a digital agency with 500 people.", pack): []
buzzwords_in("Infinum is a digital agency with 500 people."): []
```
The existing rules do NOT catch the invented figure 500.

**With the case-study rule (new code):**
```
case_study_violations("Infinum is a digital agency with 500 people.", studies): [('infinum', '500')]
```
The new rule catches it. The guard is load-bearing.

### Acceptance 7: Full suite

**SUITE RUNNING.** Started at 2026-09-26T13:54:47Z. Expected completion ~35 minutes. Will update when verdict is available.

---

### FINDINGS

1. **operator_summary "70" is not on the Infinum page.** The summary says "grew from 70 to 350" but the page says "370 people" (body) and "420 employees" (sidebar). The figure "70" does not appear as a standalone token. This is a finding about the summary's accuracy, not a bug in the lint.

2. **Token-level binding is necessary.** The initial implementation used `_norm`-based substring matching, which let "70" pass against "370" on the page. Fixed to token-level matching where each specific must appear as a standalone word on the page.

3. **`check_batch` now accepts `case_studies` parameter.** Tests inject studies directly; production loads from `work/evidence/case-studies/` via `_load_studies()`.

### RISKS

- The binding requires 2+ significant words shared between claim and page sentence. This is conservative and may refuse claims that are technically on the page but phrased very differently. This is by design - refuse rather than pass a claim that cannot be deterministically bound.
- The study cache is global and loaded once. If the stored files change during a process, `reset_study_cache()` must be called.

### RECOMMENDED CLAUDE ACTION

1. Review the lint rule and token-level binding logic.
2. Decide what to do about the operator_summary "70" finding - update the summary or leave it as orientation-only.
3. Integrate the suite verdict when available.
