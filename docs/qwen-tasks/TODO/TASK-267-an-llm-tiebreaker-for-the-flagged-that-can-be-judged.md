# TASK-267 — An LLM tiebreaker, on the flagged that CAN be judged

SIZE: M
Operator instruction, 2026-09-23: a second-stage judge over the FLAGGED
domains with the operator's ICP narrative. Verdict, confidence and a
one-sentence reason per domain. Cost reported.

## THE POPULATION IS 5,851, NOT 3,668 AND NOT 8,370

The instruction says 3,668. That was `work/stage/s3-icp.jsonl` — 24,404 rows,
`out 15,642 / in 5,094 / flagged 3,668`. **The re-judge has since run.**
`work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl`, written 2026-09-23
17:17, same 24,404 domains, reads:

    in 15,943    flagged 8,370    out 91

And the 8,370 splits into two populations that must not be sent to a model
together:

    5,851   headcount not judged (2026-09-22 amendment), geo not confirmed
    2,519   provider returned no company for this domain

**The 2,519 are unresolvable and no judge can fix them.** There is no company
behind the domain to reason about; the journal already knows this. Sending
them costs money to be told what we know. **Judge the 5,851.** Count the
2,519 separately in the report and name them as "no company data", never as
a verdict.

Re-count both files at the start of the task rather than trusting these
numbers — the re-judge ran hours before this was written and may run again.

## THE PATTERN IS ALREADY IN THE TREE — COPY IT

`scripts/stage_s3_rejudge_amended.py` is the proof of shape: read the
journal, re-decide, write a **separate** journal, print a SET diff with a
`LOST (must be zero)` assertion. Do not mutate `s3-icp.jsonl` and do not
write into the amended file. A third journal.

The judge seam is `scripts/stage_s3_icp.py:228` (`verdict, reason =
judge(info, icp)`) or a standalone pass modelled on the re-judge script.
Prefer the standalone pass: it costs nothing to re-run and cannot corrupt the
first stage.

**Note there are two qualification engines and this is the snapshot one.**
`stage_s3_icp.judge()` :111 returns `in/out/flagged`. `src/icp.py:208`
`score()` is the canonical product path with `STATUSES`/`TIERS`/`CONFIDENCE`
(:35-51). Do not mix the vocabularies; this task stays in `in/out/flagged`
and adds `confidence` and `reason` alongside.

## THE MODEL, AND THE COST

`src/llm.py` `NoModel` is the default (:149) "so nothing calls a model by
accident" — that default stays. Use `from_env()` :466 and require an explicit
opt-in flag to spend. Available: `providers/xai.py` (`grok-4.6`, :49) and
`providers/glm.py` (`glm-5.3`, :78).

Cost is plumbing that already exists, in three layers:

    llm.record_usage_since()  :867   writes rec["model_calls"]
    llm.token_usage(records)  :895   returns UNKNOWN rather than a number
                                     when ANY call lacks a count
    spendledger.check()       :156   raises BudgetExceeded
    costs.reconcile()         :234   expected vs observed

**`spendledger` records EXPECTED cost at call time** (docstring :29-32).
A report that quotes only that is quoting an estimate and must print the word
`ESTIMATED_ONLY` rather than a bare dollar figure. Cap before you fan out —
5,851 domains is a real bill.

## THE OUTPUT

Per domain: `verdict`, `confidence`, and **one sentence of reason grounded in
the row's own fields** (`employees`, `country`, `industry`, `reason`). The
rows already carry everything a judge needs, so this costs zero provider
credits beyond the model call.

**Read TASK-272's warning before writing the reason string.** A reason
generated from the verdict rather than from the evidence is how
`"scored above threshold"` once appeared on rows scoring 0.0.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: the no-company-data population is excluded from judging and
counted apart; a domain the model does not answer for keeps its original
verdict rather than defaulting to one; the cost report prints
`ESTIMATED_ONLY` when only expected cost is available; a run with no model
configured refuses loudly rather than judging nothing silently; the SET diff
asserts `LOST` is zero. Offline: the model is faked, no live call in tests.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
    work/stage/s3-icp.jsonl                             (READ ONLY)
    work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl (READ ONLY)
