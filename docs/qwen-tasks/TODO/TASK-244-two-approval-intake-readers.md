# TASK-244 — both approval intake readers, so the operator picks one

OPERATOR DECISION, 2026-09-21, Zvonimir:

> Approval intake: build both readers and I will say which Productive uses:
> (a) a Google Sheet the system writes candidates to and reads a Yes/No
> column back from; (b) a Slack flow in #productive-resonate-outbound
> (C0ADUMGQX8S) where the list is posted and approvals come back as a reply
> or reaction. Approvals are recorded per domain with the approver and
> timestamp; rejections are permanent unless Productive reverses them in
> writing.

**BUILD BOTH. Ship neither as the default.** The operator chooses, and a
reader that cannot be left switched off is a reader that made the choice.

## THE STATE ALREADY EXISTS. YOU DO NOT WRITE IT.

`src/clientapproval.py` lands on master tonight. Rebase first. Every approval
you read becomes exactly one `clientapproval.record(...)` call:

    clientapproval.record(domain, client, state, who, source, at=None,
                          reverses=None, evidence=None)

`who` is the approver's real identity as the channel gives it - a Google
account, a Slack user id resolved to a display name. `source` names the
mechanism and the artifact: `"sheet:<spreadsheet id>:<tab>"` or
`"slack:C0ADUMGQX8S:<message ts>"`. Never `"operator"`, never `"import"`.
A row whose approver cannot be identified is NOT an approval.

## (a) THE SHEET READER — `src/approvalsheet.py`

Writes the candidate export (TASK-245's columns) to a tab, reads a Yes/No
column back. Idempotent: re-reading the same sheet records nothing new.
An empty cell is PENDING, not a no. A value that is neither yes nor no is
UNKNOWN and is reported, never guessed - the register has six rows that are
the same shape as guessing.

## (b) THE SLACK READER — `src/approvalslack.py`

Posts the candidate list to `#productive-resonate-outbound` (C0ADUMGQX8S) and
reads approvals back as replies or reactions. A list too long for one message
is paged and each page carries its own stable identity, because an approval
on page 3 must resolve to the domains on page 3 and nothing else.

**Reactions are ambiguous and you must handle it rather than assume.** A
thumbs-up on a message covering forty domains approves forty domains; decide
and document that explicitly, and make a per-domain reply the precise form.
`slack_get_reactions` gives you the reacting user ids; resolve them.

## BOTH READERS

- **Rejections are permanent.** `rejected` may only be lifted by a row
  carrying `reverses` and `evidence` - the written reversal. Prove it with a
  test that tries to lift one without evidence and fails.
- **Read-only until asked.** Neither reader polls on import. Each is a
  script/entrypoint that runs when invoked.
- No PII in git. Domains are not PII; approver names are. They go to the
  gitignored store, never into a tracked file or a test fixture.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions. Every provider call in tests
is faked - no live Google or Slack call from the suite.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
