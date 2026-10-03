PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-931 — adversarially verify the boundaries the ramp now rests on

**Operator instruction, Zvonimir, 2026-09-30:** GLM adversarially verifies the
research admission boundary, provenance retention, claim licensing, and the
exact SHA of accepted fixes.

**Your job is to REFUTE these claims, not to confirm them.** A verification
that sets out to agree is worth nothing. Every claim below is asserted by me
on the SHA named; find the case where it is false.

## The SHAs

    01b7caf6  P.S. authority on the approved step; grant bound to campaign
    b946b59c  writer retry: all reasons fed back, rising temperature
    3de64b76  em4 prompt no longer asks for a benchmark
    921ad107  AUTONOMOUS_PRODUCTION approval authority
    4ae050c1  research.NEED_COPY_EVIDENCE
    4368bb46  channels.email_verdict asks under the client's policy
    e7e7de7a  for_copy threaded to execution; first real Apify run

Confirm each exists on `origin/master` and that the diff does what the
message says. A commit message is a claim, not evidence.

## Claim 1 — the approval authority is not a self-stamp

`approval.AUTONOMOUS_PRODUCTION` certifies copy no person read.

**Try to break it.** Find any `by` string that is accountable but should not
be; any path that mints the stamp without `autonomous_stamp()`; any way the
window's expiry fails to revoke it; any caller that needs
`personally_reviewed` and asks `is_accountable_approver` instead. `claude`,
`qwen`, `glm`, `system` must all still be refused. Check every one of the
three existing `is_accountable_approver` call sites, not just staging.

## Claim 2 — the evidence bar was not lowered

`MIN_RELEVANCE` 0.65 and `MIN_COPY_EVIDENCE_ROWS` 3 are unchanged, and
nothing routes around `evidence.select`.

**Try to break it.** Find a path where a WEAK row reaches a prompt; where
`_copy_evidence_missing` is bypassed; where row COUNT is used in place of
admitted count; where a duplicate page inflates the admitted count so a thin
pack passes. `sohoexp-com` has four rows and one admitted — confirm that is
what every consumer sees.

## Claim 3 — provenance is retained on every gathered row

Each row from the first real run carries `source_url`, `provider`,
`retrieved_at`, quality and relevance.

**Try to break it.** Find a row that reaches the writer with no traceable
source, or a `fact` whose text is not on the page its `source_url` names.

## Claim 4 — claim licensing still refuses what it refused

TASK-914/921's customer-outcome detection is intact and evidence-sensitive:
a refusal must VANISH when evidence licenses the claim, or the rule is a
vocabulary filter rather than a semantic one.

**Try to break it** with held-out text of your own. Do not reuse examples
from the task files; those counterexamples are burned.

## Claim 5 — the verification alignment is an alignment, not a loosening

`channels.email_verdict` now asks `lint.policy_for_record(rec)`. Measured: 63
contacts stricter, 787 looser, because the client's policy is not the
default.

**Try to break it.** Find a contact the client's policy should refuse and
this clears. Confirm the 787 are cleared by the client's OWN configured
policy and not by a default leaking through.

## Report

For each claim: REFUTED with the exact case, or UPHELD with what you tried.
"I could not find a problem" is a result; "looks fine" is not.
