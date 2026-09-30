PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-930 — batch the evidence backlog through the EXISTING canonical path

**Operator decision, Zvonimir, 2026-09-30:** the evidence bar stays. A
shortfall is a research problem, per company: *insufficient evidence → run
the canonical Apify/research path → richer sourced pack → re-evaluate →
still insufficient → HELD with the exact reason → continue.*

**And:** do not make Claude process 614 accounts one at a time, and do not
bulk-run 614 paid researches until one account has proved the path.

## The path is already proved. Do not rebuild it.

Measured on master `e7e7de7a`, `sohoexp-com` (source row 65):

    before   0 research rows, 0 admitted
    ops      people-count (free), then apify-research, reason
             `public_evidence_required_for_prospect_facing_copy`
    bounded  5 pages, 20 items, 180s, RunBudget(1)
    after    4 rows, 1 admitted

The wiring exists: `research.NEED_COPY_EVIDENCE`, `research.why(...,
for_copy=True)`, `research.run(..., for_copy=True)` and
`enrich.enrich_record(..., for_copy=True)`. **`enrich_record` is the only
call site that owns the `spend` ledger and you must go through it.** A second
research caller with its own ledger is invisible to the spend audit, and an
audit that reports clean because it watched nothing is worse than none.

## What to build

A deterministic, resumable batch controller over the accounts that
`research.why(rec, for_copy=True)` reports as `NEED_COPY_EVIDENCE` — **614 of
1,582 at the time of writing**.

1. **Order is the operator's approved source order**, from
   `work/Productive/productive_ICP_safe_to_send (1).csv`, not queue order and
   not "whatever is cheapest". `scripts/canary_candidate_walk.py` already
   walks that file and is the precedent for the ordering and the
   QUALIFIED/HELD/NOT_QUALIFIED vocabulary.
2. **A cap per run, refused rather than exceeded**, in the shape
   `enrich.Budget` and `research.RunBudget` already have. An uncapped default
   is not acceptable: `require_cap` exists because an operator's omission is
   where unbounded spend comes from.
3. **Resumable from the estate, not from a checkpoint file.** An account that
   now has enough admitted rows is simply no longer in the set, so re-running
   the command IS the resume. Do not invent a second state file.
4. **Re-evaluate after each account** and record the disposition: reached the
   bar, or HELD with the exact evidence reason and the admitted-row count.
5. **Report qualified / held / not-qualified separately.** The operator asked
   for this explicitly: the ramp counts companies ATTEMPTED, and an easy
   account must never quietly stand in for an attempted one.

## What it must not do

- **Never lower `MIN_RELEVANCE` (0.65) or `MIN_COPY_EVIDENCE_ROWS` (3).**
  Two accounts already sit 0.05 under the relevance threshold, which is
  exactly the near-miss that invites tuning. Tuning it turns a measured
  shortfall into a silent pass on every record in the estate. The floor of 3
  is a measurement: TWO IS THE NUMBER THAT FAILED on `2020companies-com`.
- Never research a REJECTED account, or one with no contact to write to.
  `_copy_evidence_missing` already refuses both; do not route around it.
- No new features, no new state, no second representation of "does this
  account need research".

## Done means

A capped run over a named set of accounts produces per-account dispositions,
spends through the canonical ledger, is safe to re-run, and a dry run
performs no actor call at all. Prove the dry run writes nothing by asserting
on the estate, not by reading the code.
