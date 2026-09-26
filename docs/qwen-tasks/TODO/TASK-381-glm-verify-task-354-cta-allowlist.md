PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-381 — GLM first-pass verification: TASK-354, the CTA link allowlist

**Operator instruction, 2026-09-26 evening.** Independent GLM verification of
work Claude already merged, per `docs/GLM-REVIEW-PROTOCOL.md` — read it
yourself and follow its procedure exactly. This file only names the target.

## Target

TASK-354's rework — merged to `origin/master` at `f3552959`, cherry-picked
from `qwen-worker-7-r78` (`src/copylint.py`, `tests/test_a_dead_cta_link_is_
refused.py`). Claude's own merge note: verified the CTA allowlist is called
from `check_batch`, which `bisonfactory.py:575`, `generate_campaign.py:340`
and `packfacts.py` already invoke; 22 new tests pass offline (resolver hook
stubbed); ran the 4 pre-existing test modules touching `copylint`/`check_batch`
and found 2 failures / 8 errors identical to master's unmodified file
(claimed pre-existing baseline debt, not caused by this change).

**Known open finding, not yours to re-discover — verify it independently
instead:** TASK-378 (docs/qwen-tasks/TODO/TASK-378-copylint-checks-half-of-
what-a-prospect-reads.md), found by Claude AFTER this merge via a separate
GLM adversarial review (`docs/glm-reviews/copylint.md`): three OLDER copylint
rules (`untraceable_company_claim`, `buzzwords_in`, the finality check) read
only `whole` (email bodies) and never `rendered` (bodies+subjects+P.S.+
LinkedIn) - so a fabricated financial claim in LinkedIn text passes
`check_batch` with `refused: False` today. **This is a DIFFERENT defect from
what TASK-354 fixed** (TASK-354's CTA rules already correctly read the full
text via `extract_urls` over `texts.append(other_prospect_text(...))`)  - your
job is to confirm TASK-354's OWN scope is sound, not to re-verify TASK-378.

## What GLM's pass must produce

1. Reproduce the allowlist proof yourself: `https://productive.io/book-a-
   demo/` resolves HEAD 200 but is refused through `check_batch` (not a direct
   `check_cta_links` call) - paste the real output.
2. Reproduce the "one HEAD per distinct URL" cache claim on a batch of 50+
   leads sharing one link.
3. Confirm or refute the "2 failures / 8 errors, identical to master" claim -
   re-run the same 4 test modules against current master yourself.
4. Confirm the `CTA_LINK_SKIP_REASON` off-switch is recorded and visible in
   the report, and cannot silently disable the allowlist check itself (only
   the network resolution half).
5. Any NEW finding with file:line.

## Result

Use the protocol's own result format and dispositions.
