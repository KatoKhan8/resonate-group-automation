PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-357 - the client file is person-centric and the queue is not

**Unblocks TASK-347, which came back BLOCKED.** Read its result block first:
`docs/qwen-tasks/REVIEW/TASK-347-the-client-file-through-the-pipeline-in-thousands.md`.

## RUN THIS IN THE MAIN CHECKOUT, NOT A WORKTREE

`C:/Users/Zvonimir/Desktop/resonate-group-automation`.

`scripts/provision_worktrees.sh` deliberately does **not** copy
`work/queue.jsonl`: it is live production state with a cross-process lock, and
twelve private copies would be twelve divergent truths. TASK-347 failed partly
because it looked for the queue in a worktree that by design has none. Do not
create one there.

## The defect

    the file    work/Productive/productive_ICP_safe_to_send (1).csv
                33,887 data rows, one row PER PERSON
                21,438 unique companies, 24,710 unique email domains
                columns: Url, First Name, Last Name, Job Title, Headline,
                         Company, Industry, Location, Work Email,
                         Work Email Status

    the queue   one record PER COMPANY, contacts in an array

`src/ingest.py` expects `company, domain` and **deduplicates by domain.** Importing
this file as-is discards roughly 12,400 rows as duplicate domains — when those
rows are in fact the additional decision makers at companies we already have.

That is exactly backwards from what the architecture wants.
`docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md`: the account is the unit, and we
want **2-3 relevant decision makers inside the same company**. This file already
contains them; the importer throws them away.

## Build

    src/ingest.py     MODIFY, or a new importer beside it - decide from the code
                      and say which you chose and why.
    tests/test_a_person_centric_csv_becomes_one_record_per_company.py   NEW

Group rows by **domain extracted from the work email**, not by the `Company`
string. 21,438 company strings against 24,710 email domains means the two
disagree, and the domain is the canonical key everywhere else in this system.
Attach each person as a contact on that company's record.

Carry per contact: name, job title, headline, LinkedIn `Url`, work email and its
status. Carry per company: industry, location.

**The LinkedIn column is TASK-311's** - do not duplicate its work; if 311 has
landed, use what it built.

## The rules that govern this

- **`work/` never reaches git.** 33,887 real people. Report counts and
  percentages, never rows. Not in the result block, not in a test fixture, not in
  a doc.
- **Touch the queue only through `src/store.py`.** Never write `queue.jsonl`
  directly.
- **Never delete a queue record.** Drop it with a reason.
- **Suppression first.** The 76 recipients suppressed after the 09-23 incident,
  and every existing unsubscribe, must not be re-imported as fresh contacts.
  Check against suppression BEFORE writing, and report the count skipped.
- **A contact already on a record is not a new contact.** Importing must be
  idempotent: running it twice must not double the contacts. Key on the email.
- **No paid call.** This task imports and groups. It spends nothing - no MX, no
  verification, no enrichment. That is TASK-347's, after this lands.

## Acceptance - RUN each, paste real output

1. Grouping is by domain and multiple contacts land on one record:

    py -3 -c "import sys;sys.path.insert(0,'.');\
    # import a 500-row slice, then:\
    print('records created, contacts attached, max contacts on one record')"

   Report: rows in, records created, contacts attached, **max contacts on one
   record**, and the distribution (how many records have 1, 2, 3, 4+ contacts).
   The 2-3-decision-makers goal is testable against that distribution.

2. **Nothing is lost silently.** rows in == contacts attached + skipped, with
   every skip carrying a reason. Assert the arithmetic balances; a row that
   vanished without a reason is a failure.

3. **Idempotent:** import the same slice twice, assert the contact count is
   identical after the second run.

4. **Suppressed addresses are not imported.** Plant a suppressed address in a
   fixture slice, assert it is skipped and the reason is recorded.

5. **The guard is seen to fail:** revert the domain grouping so it dedups by
   domain and drops, confirm the test FAILS naming the dropped contacts, restore.
   Confirm the revert landed. Paste both runs.

6. Queue integrity: record count before and after, no record deleted, and
   `src/store.py` is the only writer.

7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names).

## What this task may NOT do

- Do not spend a credit. No MX, no verifier, no enrichment, no model call.
- Do not commit anything from `work/`. Counts only.
- Do not import the whole file. A slice big enough to prove the grouping, then
  stop and report - the full import is TASK-347's after this lands.
- Nothing sent, nothing activated.
