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
