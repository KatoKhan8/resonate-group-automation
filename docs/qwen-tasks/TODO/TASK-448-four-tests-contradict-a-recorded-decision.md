PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-448 — four tests assert the opposite of a recorded operator decision

Off the critical path. Evidence and full diagnosis:
`docs/SUITE-TRUTH-2026-09-27-NIGHT.md`. Each of these four fails on master in
BOTH full and standalone mode, each was verified pre-existing at `1f4d464c` by
two independent parties, and **each is a gap in the committed suite baseline
rather than a regression.** The baseline is short by these 4 names.

## THE RULE FOR THIS WHOLE TASK

**Every one of these is fixed by making the test assert the invariant ACTUALLY
IN FORCE. None is fixed by deleting an assertion, loosening it, skipping the
test, or whitelisting the specific value that trips it.** Never delete a
legitimate test for green CI. If you conclude a test cannot be fixed without
weakening it, STOP and report that — it is a finding, not a licence.

## 1. An approved offer is not an invented offer

`tests/test_an_offer_cannot_be_invented.py::TestApprovalRefusal::test_approval_status_is_not_defaulted_to_approved`

It asserts that **no** offer in the library carries `approval_status: approved`.
It fails on `OFFER-A-ECONOMIC-BUYER`, because **the operator approved Offers A
and B on 2026-09-27** — recorded with `approved_by: Zvonimir`, `approved_on`,
`approved_at_sha`, and an `approval_history` that keeps the v1 approval with
`carried_forward: false`.

The test's own stated intent is right: "production does not approve its own
offers." What it actually asserts is that nothing is ever approved, which forbids
the operator from approving anything — so it can only pass in a world where the
product never ships.

**Fix it to assert the intent:** an offer with `approval_status: approved` MUST
carry named human attribution and provenance (`approved_by`, `approved_on`, and
the sha it was approved at); an offer without that attribution must NOT be
readable as approved. That is a STRONGER test than the one there now, because it
would catch the thing actually feared — a defaulted or self-granted approval —
which today's version cannot distinguish from a legitimate one.

Read `config/clients/productive-offers.yaml` for the real shape. Do not change
that file: it is the canonical record of an operator decision.

## 2 and 3. The client's own domain is not a prospect domain

`tests/test_fixture_hygiene.py::TestNoRealDataAnywhereInGit::test_no_real_client_prospect_or_roster_domain`
`tests/test_fixture_hygiene.py::TestNoRealDataAnywhereInGit::test_every_email_address_is_on_a_reserved_domain`

Both fail on **`productive.io`** appearing in tracked files, among them
`src/copylint.py`, `docs/qwen-tasks/TODO/TASK-428-*.md` and
`docs/status/STATUS-2026-09-27-1223.md`.

**This is NOT a PII leak — that was checked, not assumed.** `productive.io` is
the client's own public domain and the **single approved CTA**,
`https://productive.io/get-started/`, operator-approved 2026-09-26 and recorded
as "THE ONLY allowed CTA link". It belongs in the code and the docs.

The test cannot tell three different things apart: a PROSPECT's domain (must
never be committed), a ROSTER domain, and the CLIENT's own public domain and CTA
(must be committed, because the CTA allowlist is code). Teach it the difference.

**Keep the guard's teeth.** The module exists because a real LinkedIn vanity name
reached a committed file this week and this test caught it — it is doing its job
and it must still catch that. Prove both directions: a prospect-looking domain
still fails the test, and the client's own approved CTA does not.

## 4. The cadence branch test

`tests/test_the_cadence_reacts_to_what_the_prospect_did.py::ThePlannerReadsTheBranch::test_the_meeting_reaches_the_send_gate_too`

Diagnose before changing anything. Note the sibling test in the same module IS a
baseline name, so the module is partly known-red; establish what THIS test
asserts, whether the behaviour it wants is the behaviour now in force, and which
side is wrong. Report the diagnosis even if the fix turns out to be one line.
The canonical cadence is five emails on days 1/4/8/12/21 and five LinkedIn steps
on 1/3/6/10/15; the 13 stale stored cadence declarations stay REFUSED by operator
decision (2026-09-27) and are not to be migrated.

## ACCEPTANCE

1. All four named tests pass, and **for each one you state which side was wrong
   and why** — the test or the code. A fix with no such sentence is not accepted.
2. For each, a MUTATION: break the invariant the test now asserts and confirm
   THAT test fails for the intended reason, with no other guard firing first.
   Assert the file changed before running; this tree is CRLF, so a text-mode
   rewrite that normalises to LF is not a restoration.
3. **No new failing name anywhere in the suite.** Diff failing test NAMES, never
   counts, and compare like with like: `py -3 -m tests.offline` and per-module
   runs are DIFFERENT harnesses and are not comparable. Use
   `scripts/suite_baseline.py`.
4. **Do not touch `docs/state/SUITE-BASELINE-2026-09-26.txt`.** Report that these
   four names should be added when the baseline is next regenerated at a named
   SHA in daylight; do not regenerate it yourself and never adopt a larger one.
   228 is never a baseline, and neither is 197.
5. `config/clients/productive-offers.yaml` is NOT edited.

Provider writes 0, never call a real provider, freeze in force, `sending.live`
off for productive. Do not touch `src/bisonfactory.py`, `src/heyreachfactory.py`,
`src/sequenceplan.py`, `src/generate.py`, `tests/test_generate.py`,
`src/packfacts.py`, `src/ingest.py` or `src/copylint.py` — other work is in those
files. **`src/copylint.py` is reserved, so if fixing 2/3 needs a change there,
report it instead of editing.**
