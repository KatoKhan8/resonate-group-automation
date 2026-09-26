PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-382 — GLM first-pass verification: TASK-367, the offers block (NOT merged)

**Operator instruction, 2026-09-26 evening.** Independent GLM verification,
per `docs/GLM-REVIEW-PROTOCOL.md` — read it yourself and follow its
procedure exactly. This file only names the target.

## Target, and why this one is different from the other three

TASK-367 is **NOT on master.** Claude reviewed `qwen-worker-4-r78` and found
the rename, the two-record `offers:` block, the `NotApproved` gate and the
`campaignstrategy` wiring all correct — but blocked the merge because
`OFFER-A-ECONOMIC-BUYER.cta_link` is `https://productive.io/book-a-demo/`,
the exact URL the standing "ONE LINK ONLY" operator decision withdrew. A
REWORK section is appended to `docs/qwen-tasks/TODO/TASK-367-a-real-offers-
block-that-owns-persona-to-offer.md` and a Qwen worker may already be running
it when you start.

**Your job is to verify Claude's blocking finding is correct, not to grade
the rework** (which may not exist yet, or may be mid-flight on another
worker). Work from branch `qwen-worker-4-r78` (`git fetch origin
qwen-worker-4-r78`), the pre-rework state.

## What GLM's pass must produce

1. Confirm, by reading the branch's `config/clients/productive-offers.yaml`
   yourself, that `OFFER-A-ECONOMIC-BUYER.cta_link` is indeed
   `https://productive.io/book-a-demo/`.
2. Confirm this URL is not `https://productive.io/get-started/` (the sole
   standing allowlisted link per TASK-354).
3. Independently verify the parts Claude called correct: capability rename
   (6 records survive), the offers block has exactly 2 records, `NotApproved`
   still raises, both offers are `pending`, `capability_by_persona` still
   owns angle order independent of offer assignment. Reproduce at least the
   NotApproved and pending-status checks yourself rather than reading the
   worker's own acceptance output.
4. If a rework has landed on this branch or a successor by the time you run
   this, verify the fix directly: does `OFFER-A-ECONOMIC-BUYER.cta_link` now
   read `https://productive.io/get-started/`, and does the merged CTA
   allowlist (on master, `src/copylint.py`) actually refuse the OLD value if
   fed to it?
5. Any NEW finding with file:line.

## Result

Use the protocol's own result format and dispositions. State plainly whether
this branch is safe to merge as of your read, or still blocked and why.
