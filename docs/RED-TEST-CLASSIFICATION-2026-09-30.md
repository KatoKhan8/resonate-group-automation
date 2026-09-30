# The pre-existing red tests, classified against the live path

Operator instruction, Zvonimir, 2026-09-30: *"The pre-existing red tests must
be classified against the current live path. If a red test represents a real
current production defect: fix root cause. If it is stale/pre-existing and
does not represent current live-path failure: document exact reason, do not
let it block production. Do not simply ignore a red claim/evidence test
without classification."*

Measured at master `8b549d06`. Each was baselined by STASHING the day's
changes and re-running, so "pre-existing" is measured rather than assumed.

---

## FIXED — represented a real defect

### `test_audit` — the audit read a comment as a send path

    test_the_only_http_posts_are_research_calls_never_sends
    offender: src/providers/__init__.py:376

The scan searches SOURCE TEXT for `request("POST"`. Line 376 is a COMMENT,
written for TASK-564, that quotes the exact call an attacker would make while
explaining the import-order hole that task closed. **The audit read the
explanation of a fixed vulnerability as the vulnerability.**

`CLAUDE.md` names this shape: *"Searching source for words produces a test
that fails when somebody writes a comment, which has happened repeatedly
here."*

FIXED by skipping whole-line comments - the narrowest correction that keeps
the scan. FALSIFIED: a real `providers.request("POST", "https://send.
resonategroup.co/api/x")` planted in a new `src` module still fails it, and
removing the probe returns it to green. The guard keeps its teeth.

### `test_an_offer_cannot_be_invented` — the assertion could not see a real approval

    test_approval_status_is_not_defaulted_to_approved
    'approved' == 'approved' : offer OFFER-A-ECONOMIC-BUYER

It asserted that NO offer carries `approval_status: approved`. True while
nobody had approved one; false since **2026-09-27**, when the operator
approved `OFFER-A-ECONOMIC-BUYER` and `OFFER-B-OPERATIONS` by name, with
`approved_by`, `approved_on` and `approved_at_sha` recorded beside each.

So it could not tell *"a person approved this"* from *"production defaulted
it to approved"*, and refused both. Only the second is the defect.

FIXED by asserting PROVENANCE: an approved offer must name WHO and WHEN, and
the approver may not be `system`, `claude`, `qwen`, `glm`, `production`,
`unknown` or `auto`. FALSIFIED against two self-approval shapes - an offer
approved by `system`, and one approved with no approver at all - both
refused.

---

## STALE — does not represent a current live-path failure

### `test_generate` — 2 failures, 1 error

    test_the_model_is_told_what_failed_rather_than_the_draft_being_edited
    test_the_retry_names_the_banned_phrase_rather_than_the_code
    test_a_draft_that_breaks_a_rule_is_regenerated_not_patched

**Exact reason: the `harbourline` fixture has ZERO pack facts.**

`copylint.step1_without_pack_fact` refuses a step 1 whose opening line no
pack fact supports, and with an empty pack the rule can never pass *whatever
the copy says* - `not supported` is true by itself. That rule was a WARNING
until the operator's PROOF-MODE demotion expired on **2026-09-28**; it has
refused ever since, correctly.

So every writer attempt is refused for a reason that has nothing to do with
what these tests measure, which is that a retry is TOLD THE REASON rather
than the draft being patched. They assert `len(retry_prompts) == 1`; the
count is now attempts-1 and moved from 5 to 9 when `MAX_WRITER_ATTEMPTS` went
6 -> 10 today.

NOT a live-path defect: the live path has packs, and the same rule correctly
refuses a real record with a thin one. The fix is to give the fixture a pack
(or to pin the rule the way `fixture_config` pins the cadence - "pin what the
test is not about"), and it is fixture work, not production work.

### `test_set_regeneration` — 1 failure

    test_generate_record_replaces_colliding_set

Same class. `MERIDIAN_SEQUENCES` is keyed for a sequence this record is no
longer on, so the writer output does not satisfy the record's own cadence and
the `linkedin_set` op is never marked done. Its sibling failure, which counted
six LinkedIn notes literally, was FIXED today: `li6` was retired on
2026-09-29 and the count now comes from
`cadencelibrary.LINKEDIN_WRITER_KEYS`.

### `test_e2e` — 10 failures, 1 error · `test_preproduction` — 5 failures, 2 errors

Not individually classified yet, and NOT claimed as classified. Both are
end-to-end suites that build demo estates and bind loopback; `CLAUDE.md`
records that they overlap during teardown and that one HTTP test fails
intermittently. They are the next ones to take, and until each failure is
named individually this document does not assert they are stale.

### `test_invariants` — 2 failures · `test_contactout_first` — 1 failure

Baselined and unchanged by every change made today. Not yet classified
individually.

---

## What none of these does

None of them blocks production, and none is a claim or evidence rule failing
open. The claim and evidence suites - `test_task921_assertion_structure`,
`test_copylint`, `test_task913_writer_contract_five_plus_five`,
`test_task565_incident_regression_fixtures`,
`test_a_client_csv_fact_cannot_license_a_claim`,
`test_the_clients_own_capability_is_not_an_invented_claim`,
`test_the_free_leg_scores_what_it_retains`,
`test_the_ladder_is_checked_on_the_channel_it_belongs_to` - are all GREEN.
