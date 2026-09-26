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

---

## RESULT

**STATUS:** DONE
**ARTIFACT KIND:** finding (independent verification)
**START POINT:** `origin/qwen-worker-4-r78` at commit `835673af`
**VERIFICATION DATE:** 2026-09-26

### 1. Claude's blocking finding — CONFIRMED

`config/clients/productive-offers.yaml` line 29 on branch `qwen-worker-4-r78`:

    cta_link: https://productive.io/book-a-demo/

This is **NOT** `https://productive.io/get-started/`, the sole allowlisted URL.
The two URLs are different strings. Independently reproduced.

### 2. The allowlist refuses the old value — CONFIRMED

Master's `src/copylint.py` lines 632-635:

    CTA_LINK_ALLOWLIST = frozenset({
        "https://productive.io/get-started/",
    })

Reproduced programmatically:

    check_cta_links(["https://productive.io/book-a-demo/"], resolve=False)
    -> not_allowlisted: ["https://productive.io/book-a-demo/"]

The lint would refuse this URL at render time. Fail-closed works correctly.

### 3. Claude's positive findings — ALL CONFIRMED

| Check | Evidence | Verdict |
|-------|----------|---------|
| 6 capabilities survive rename | `capabilities:` block has 6 records: OFFER-PM-001, OFFER-TT-001, OFFER-BU-001, OFFER-RP-001, OFFER-BI-001, OFFER-PR-001 | PASS |
| Exactly 2 offers | `offers:` block has 2 records: OFFER-A-ECONOMIC-BUYER, OFFER-B-OPERATIONS | PASS |
| `NotApproved` still raises | `src/offers.py:40` defines class; `src/offers.py:100` raises it when `approval_status != 'approved'`; simulated `for_campaign(503, require_approved=True)` raises on OFFER-A-ECONOMIC-BUYER (status=pending) | PASS |
| Both offers are `pending` | Verified by parsing the YAML: both have `approval_status: pending` | PASS |
| `capability_by_persona` owns angle order | `config/clients/productive.yaml:359` has `capability_by_persona:`; `src/campaignstrategy.py:66-67` documents that angle order comes from it, not from the offer | PASS |

### 4. Rework status — NOT YET APPLIED

No commit on `qwen-worker-4-r78` fixes the CTA link. The top commit remains
`835673af` (TASK-367 to DONE). No successor branch (`qwen-worker-4-r80`) has
the TASK-367 changes at all — it still has the old 6-record `offers:` format.
The REWORK section exists on master in the TASK-367 task file but has not been
implemented.

### 5. New finding

**Internal contradiction within the same YAML file.** The branch's
`config/clients/productive-offers.yaml` line 273 says:

    link: https://productive.io/get-started/      # THE ONLY allowed CTA link, 2026-09-26

...in the `mechanisms.demo.link` field. But line 29 of the **same file** has
`https://productive.io/book-a-demo/` as `OFFER-A-ECONOMIC-BUYER.cta_link`. The
file contradicts its own stated rule within 250 lines.

### Disposition

**BLOCKED — Claude's finding is correct.** The branch is NOT safe to merge.
`OFFER-A-ECONOMIC-BUYER.cta_link` must be changed to
`https://productive.io/get-started/` before merge. The rework instructions on
master are correct and sufficient.

### Reproducible commands

    git fetch origin qwen-worker-4-r78
    git show FETCH_HEAD:config/clients/productive-offers.yaml | grep book-a-demo
    # -> line 29: cta_link: https://productive.io/book-a-demo/

    git show FETCH_HEAD:config/clients/productive-offers.yaml | grep "THE ONLY"
    # -> line 273: link: https://productive.io/get-started/  # THE ONLY allowed CTA link

    python -c "from src.copylint import CTA_LINK_ALLOWLIST; print('https://productive.io/book-a-demo/' in CTA_LINK_ALLOWLIST)"
    # -> False
