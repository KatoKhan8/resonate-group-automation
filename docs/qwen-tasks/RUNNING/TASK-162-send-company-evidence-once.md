PRIORITY: P1
DEPENDS:

# TASK-162 - implement company-level evidence reuse

TASK-150 measured it and the answer was total: every company-derived key in
the generation context - `company`, `domain`, `facts`, `public_evidence`,
`research` - is BYTE-IDENTICAL across every contact at the same record. At 2.5
contacts per domain that is 2.5x the input tokens for the same text.

`docs/COMPANY-EVIDENCE-REUSE-2026-09-15.md` has the measurement and a design.
This implements it.

## WHAT MUST HOLD

- **Provenance survives.** Every fact keeps `source_url` and `retrieved_at`.
  `claims.py` reads `rec["research"]` directly and a compaction that breaks the
  link between a sentence and its source breaks the claims gate.
- **Freshness survives.** `research.ttl_for` gives short-lived fields 3 days
  and long-lived 30. A cached company object must not make stale evidence look
  current.
- **Prove it is consumed.** Drive the test through `generate.context_for` -
  the function production calls. Then delete your change and re-run: if the
  tests still pass they prove nothing. Put the counterfactual in the result.
- **Measure the saving.** Tokens per company before and after, on a real
  multi-contact record, named by record id.

## THE CEILING, SO NOBODY OVERSELLS IT

TASK-143 measured that a draft references an evidence fact 7.3% of the time
even when the evidence is good. This is a COST change, not a quality change.

## FILES ALLOWED

    src/generate.py   src/research.py   tests/

## RULES

No provider writes. Do not write to `work/`. Do not run generation against the
real queue. Do not weaken a gate to make a test pass.
