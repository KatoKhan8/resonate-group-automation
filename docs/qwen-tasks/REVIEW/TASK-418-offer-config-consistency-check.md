PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-418 — Offer Config Consistency Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `offer-config-consistency-check`.

Read `config/clients/productive-offers.yaml` end to end and check for
internal contradictions the way TASK-382's GLM review found one (a "THE
ONLY allowed link" comment coexisting with a different link elsewhere in
the same file). Report every such contradiction found, file:line, quoting
both sides. Acceptance: a clean pass reports "none found" honestly; any
contradiction found is quoted exactly, both sides.

---

## RESULT BLOCK

**STATUS:** DONE — two contradictions found
**COMMIT SHA:** (pending)
**TESTS:** read-only analysis, no tests applicable
**FILES CHANGED:** config/clients/productive-offers.yaml (read only, not modified)
**ARTIFACT KIND:** finding

### FINDINGS

**Contradiction 1 — `missing` claims no case studies exist; `evidence` lists 11 of them**

Side A (line 297-298):
```yaml
  customer_case_studies:
    gap: customer case studies
    detail: no documented customer outcomes or case studies available
```

Side B (lines 313-404, 11 entries, all `status: CLIENT_APPROVED`):
```yaml
# ---------------------------------------------------------------- evidence
# Public case studies published by Productive, retrieved 2026-09-26.
#
# STATUS: CLIENT_APPROVED. The client confirmed on 2026-09-26 that these may be
# NAMED in cold outreach, with the figures published on those pages.
```
Entries: Infinum (line 322), Makerstreet (line 329), DotControl (line 336), Hike One (line 343), Saffron (line 350), BICG (line 357), Porsche Digital Croatia (line 364), Tandem X Visuals (line 371), Flatline Agency (line 378), DonQ (line 385), Medico Digital (line 392).

Each has a name, URL, retrieval date, CLIENT_APPROVED status, and operator_summary. The `missing` block says none are available; the `evidence` block shows 11 are. The gap entry should say either "no stored page_text for case study claims" (which is true — all have `page_text: null`) or be removed, because "no documented customer outcomes or case studies available" is false.

---

**Contradiction 2 — "THE ONLY allowed CTA link" vs. public tools declared "usable as a low-stakes CTA" at a different URL**

Side A (line 462):
```yaml
    link: https://productive.io/get-started/      # THE ONLY allowed CTA link, 2026-09-26
```

Side B (lines 441-456):
```yaml
# Public free tools on productive.io, usable as a low-stakes CTA.
# VERIFIED (public source), retrieved 2026-09-26.
public_tools:
  agency_valuation_calculator:
    name: Agency Valuation Calculator
    url: https://productive.io/
    ...
  billable_hours_calculator:
    name: Billable Hours Calculator
    url: https://productive.io/
```

The mechanisms section declares `https://productive.io/get-started/` as "THE ONLY allowed CTA link." The public_tools section declares two tools "usable as a low-stakes CTA" with URLs pointing to `https://productive.io/` (the homepage) — a different URL. Either the public tools are not CTAs (and the section comment is wrong), or the "ONLY allowed CTA link" comment is wrong, or the public tool URLs should be the same `/get-started/` link.

### RISKS

Both contradictions are data-level, not code-level. Contradiction 1 could mislead a generation task into thinking no case studies exist and skipping them entirely. Contradiction 2 could cause a lint or gate to reject a public-tool CTA or, conversely, to allow a non-get-started link that was meant to be forbidden.

### RECOMMENDED CLAUDE ACTION

1. Fix `missing.customer_case_studies.detail` to say what is actually missing: `page_text` for traceable claims, not the case studies themselves.
2. Clarify the public_tools section: either remove "usable as a low-stakes CTA" from the comment, or amend the "THE ONLY allowed CTA link" comment in mechanisms to acknowledge the public tools as an exception, and pin the public tool URLs to `/get-started/` if that is the intent.
