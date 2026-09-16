PRIORITY: P0
DEPENDS:

# TASK-163 - the free path from `queued` to an ICP verdict, for 316 records

## WHERE THIS SITS

TASK-160 proved the 250 unqualified records were not a defect: no runner was
invoked after ingestion. The snapshot now reads:

    drafted 44   held 36   dropped 125   approved 3   queued 316   verified 26

316 records sit in `queued`, lane `domains`, with **no `company_facts`, no
`research`, no `stages`**. TASK-160's recommendation was to run qualify.

Claude did not run it, for one measured reason.

## THE REASON, AND THE QUESTION

`src/qualify.py` says a rejected company consumes zero person credits, and
`stage_qualify` in `src/run.py` says `qualify.company` spends nothing. So
qualify is free. But `qualify._release_stale_icp_drop` exists because
**`dropped` is terminal**.

A record with no `company_facts` and no `research` is a record ICP judges on
nothing.

    If ICP without evidence returns `dropped`, running qualify on 316 records
    permanently destroys every good company in that batch.

That is the question. Answer it from the code and from a bounded measurement,
not from an opinion:

1. Read `src/icp.py` and `src/icpstructural.py`. With `company_facts` absent
   and `research` absent, what verdict does a record get? Trace the actual
   branch. Name the function and line that decides it.
2. Is there a free research step that populates `company_facts` before ICP
   sees the record? `src/research.py` has a `webfetch` path (free HTTP) and an
   Apify path (paid). Does `stage_qualify` reach either? Does `stage_enrich`
   with `--cap 0` run free webfetch research and refuse the paid calls? Prove
   it from the code path, then prove it by running it.
3. Measure it on FIVE records. `--limit 5`. Report the verdict each of the
   five received and whether any reached `dropped`.

## THE TRAP

A record that ICP marks `unqualified` or `review` is recoverable. A record it
marks `dropped` is not. Those three outcomes look equally like "ICP ran" from
a summary line. Distinguish them per record.

Do not report that qualify is safe because the docstring says it spends
nothing. Money and reversibility are different questions, and only the second
one matters here.

## THE DELIVERABLE THAT MATTERS

One of two answers, stated plainly:

  A. The free path is `<exact command>`, it populates evidence before ICP,
     and no evidence-free record can reach `dropped`. Here are the five
     measured verdicts.

  B. Evidence-free ICP can drop. The 316 must be researched first, the free
     research command is `<exact command>`, it costs nothing, and here is
     what it populated on five records.

Claude runs the full 316 on your answer. Getting this wrong destroys the
batch, so if you cannot prove it, say which measurement is missing.

## WHAT YOU MAY NOT DO

- No provider writes. No paid provider calls. No Apify run, no enrichment
  credit, no model call that costs money.
- Do not run any stage over more than 5 records.
- Do not weaken ICP, and do not propose weakening it to raise throughput.

## FILES ALLOWED

    docs/FREE-ICP-PATH-2026-09-16.md   (new)
    scripts/task163_*.py

## FILES FORBIDDEN

    src/   config/
