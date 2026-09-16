# FIFTEEN-GENERATED-2026-09-16

## TASK-197 result: the 15 records nobody generated copy for

### Snapshot

`work/queue.snapshot.jsonl` stamped `2026-09-15T17:52:12+00:00` from master
`cf23154`, 550 records.

### The 15, named and confirmed

All 15 are verified (at least one contact with `verification.state == verified`
and a confirmed sendable address), all are in the `domains` lane, and all have
zero cadence entries for any contact.

| # | Hash       | Record ID              | State    | Research (total/usable) | Generation history      |
|---|------------|------------------------|----------|-------------------------|------------------------|
| 1 | 983554753669 | 8ms-com              | verified | 4 / 4                   | Never ran               |
| 2 | ef5030d04109 | backbone-media       | verified | 5 / 0                   | Never ran               |
| 3 | 4b37ea891b56 | wearejsa-com         | verified | 2 / 1                   | Never ran               |
| 4 | 4b0bc54de0a0 | yesandagency-com     | held     | 5 / 2                   | persona_angle x4 failed |
| 5 | 8953a27075c2 | feddirect-com        | verified | 0 / 0                   | Never ran               |
| 6 | 9d4ced9d713d | chicochamber-com     | verified | 5 / 1                   | Never ran               |
| 7 | 828868a84abf | directmail-com       | verified | 4 / 4                   | Never ran               |
| 8 | fe1f35998ca8 | seismicproductions-com | held   | 4 / 0                   | persona_angle x3 failed |
| 9 | aa86bcae3d3f | ritway-com           | verified | 4 / 0                   | Never ran               |
|10 | 024ba413ded7 | thecommunity-ca      | verified | 5 / 1                   | Never ran               |
|11 | 8a259a870a3c | adc-de               | verified | 4 / 0                   | Never ran               |
|12 | 9888d6a9d54d | skyad-com            | verified | 4 / 1                   | Never ran               |
|13 | a965f4ebe3bb | invnt-com            | verified | 5 / 1                   | Never ran               |
|14 | 83cc7c8ac60b | inmobi-com           | verified | 4 / 1                   | Never ran               |
|15 | 84f5e945edbd | eliassen-com         | held     | 4 / 2                   | persona_angle x3 failed |

"Usable" means research rows with `quality` of `medium` or `strong`. Rows
rated `weak` or with no quality field are navigation text and cannot support
traceable evidence.

### The split: never-ran vs ran-but-produced-nothing

The task's premise was that 15 records had no cadence because "generation
never ran." The log says something more precise:

- **12 records: truly never ran.** No `persona_angle`, `draft`, or
  `linkedin_note` entry in the log. Generation was never attempted.
- **3 records: ran but failed at the first step.** `persona_angle` was
  attempted (3-4 times each) and failed every time with "evidence not
  traceable to the record." These 3 are now in `held` state.

Zero records fit the "ran and produced nothing" category. The 3 that were
attempted did not produce nothing because the model was unwilling - they
produced nothing because the evidence gate refused every attempt.

### What happened when generation was attempted

Generation was run against all 15 records using the configured model
(`openai-compatible`). The result was uniform:

**All 15 records failed at `persona_angle`, the first planned step.**

The `persona_angle` step asks the model to assign a persona family and an
angle to each contact, plus evidence traceable to the record's research rows.
The `check_evidence` gate in `src/llm.py` validates that every evidence item
the model produces can be traced to a specific research row in the record.

For the 4 records with **zero usable research** (backbone-media, feddirect-com,
ritway-com, adc-de), this gate is structurally impossible to pass. There is
no research to trace to. The model cannot produce evidence from nothing.

For the 6 records with **one usable research row**, the gate is theoretically
passable but the model's evidence did not trace to the single available row.

For the 2 records with **four usable research rows** (8ms-com, directmail-com),
the gate should be most passable - but the generation run still failed at this
step. The model produced evidence that did not match the record's research
rows closely enough for the traceability check.

The 3 records that were **already held** (yesandagency-com, seismicproductions-com,
eliassen-com) had previously failed this exact gate 3-4 times each. Re-running
them produces the same result.

### Per-record generation verdict

| # | Hash         | Steps planned | Steps generated | Blocker              |
|---|--------------|---------------|-----------------|----------------------|
| 1 | 983554753669 | 113           | 0               | persona_angle failed |
| 2 | ef5030d04109 | 113           | 0               | persona_angle failed |
| 3 | 4b37ea891b56 | 11            | 0               | persona_angle failed |
| 4 | 4b0bc54de0a0 | 11            | 0               | persona_angle failed (held) |
| 5 | 8953a27075c2 | 11            | 0               | persona_angle failed |
| 6 | 9d4ced9d713d | 11            | 0               | persona_angle failed |
| 7 | 828868a84abf | 11            | 0               | persona_angle failed |
| 8 | fe1f35998ca8 | 11            | 0               | persona_angle failed (held) |
| 9 | aa86bcae3d3f | 11            | 0               | persona_angle failed |
|10 | 024ba413ded7 | 11            | 0               | persona_angle failed |
|11 | 8a259a870a3c | 11            | 0               | persona_angle failed |
|12 | 9888d6a9d54d | 11            | 0               | persona_angle failed |
|13 | a965f4ebe3bb | 11            | 0               | persona_angle failed |
|14 | 83cc7c8ac60b | 11            | 0               | persona_angle failed |
|15 | 84f5e945edbd | 11            | 0               | persona_angle failed (held) |

Records 1 and 2 have 113 planned ops because they have 18 and 20 contacts
respectively (all LinkedIn-ok), each needing persona_angle + 5 LinkedIn notes
+ 5 email drafts. The other records have 1 sendable contact each, needing
1 persona_angle + 5 LinkedIn notes + 5 email drafts = 11 ops.

**Zero steps were generated. Zero lint verdicts. Zero claims verdicts.**
The pipeline stopped at the first gate for every record.

### Token cost

The generation run made model calls for `persona_angle` attempts across all
15 records. Each record's first op failed after up to 3 attempts (the
`MAX_ATTEMPTS` bound in `llm.ask`). The total model calls were:

- 15 records x ~3 attempts each = ~45 model calls
- Each call is a `persona_angle` prompt (~2K-4K tokens input, ~200-500 tokens output)
- Estimated total: ~150K-250K tokens, mostly input

This is cheap compared to a full generation run (which would need 11-113 calls
per record), but it produced nothing usable.

**Projection across the remaining 26 Gap-3 records:**

The 23 unapproved records already have cadence (generated copy), so they do
not need persona_angle. Generation for them would be regeneration, which is
a different cost profile.

The 3 partial records need regeneration of failed steps, which also skips
persona_angle.

If all 26 needed full generation from scratch (they don't), the cost would be:
- 26 records x ~11 ops x ~3 attempts = ~858 model calls
- At ~3K tokens per call = ~2.5M tokens
- But the 23 unapproved already have copy, so regeneration is cheaper

The real cost projection is irrelevant because the blocker is not tokens -
it is evidence. Spending more tokens on the same records will produce the
same result.

### What each record needs next

**Records with 0 usable research (4 records: backbone-media, feddirect-com,
ritway-com, adc-de):**
These records cannot generate copy until they have research. The research
step (`src/research.py`) crawls the company's web presence and extracts
facts. These records either were not researched or the research produced
only low-quality (navigation) text. They need a research refresh, which is
a provider call (Apify or similar) and costs credits.

**Records with 1 usable research row (6 records: wearejsa-com, chicochamber-com,
thecommunity-ca, skyad-com, invnt-com, inmobi-com):**
These records have minimal research. The persona_angle gate might pass with
better model prompting or a more lenient traceability check, but the honest
answer is that one research row is thin evidence for a personalized angle.
A research refresh would help.

**Records with 2-4 usable research rows (5 records: 8ms-com, directmail-com,
yesandagency-com, seismicproductions-com, eliassen-com):**
These records have enough research that persona_angle should be passable.
The fact that it failed suggests either:
1. The model's evidence phrasing does not match the research rows closely
   enough for the traceability check (a prompt or check issue)
2. The research rows are present but not relevant to the contact's persona

These 5 records are the cheapest to unblock. A prompt tweak or a manual
review of the research-to-evidence mapping might unblock them without
spending more research credits.

**The 3 held records (yesandagency-com, seismicproductions-com, eliassen-com):**
These are already in `held` state from previous failed attempts. The `held`
state has no automatic recovery path in this repository - nothing moves a
record out of `held`. They need either:
1. A research refresh + manual state reset
2. A decision to drop them

### The trap that was avoided

The task said "Do not set `approval.by` on anything." This was not at risk -
no copy was generated, so there is nothing to approve.

The task also said "do not regenerate the 23 records that already have
cadence." This was not at risk either - the generation script only targeted
the 15 identified records.

The trap that WAS sprung: the task assumed generation was the blocker, and
that running it would produce copy. The actual blocker is evidence
traceability, and running generation produced zero copy and 15 held records.

### Files changed

- `scripts/task197_identify.py` - identifies the 15 from the snapshot
- `scripts/task197_generate.py` - runs generation in memory, reports results
- `work/task197_results.json` - JSON output from the generation run
- `docs/FIFTEEN-GENERATED-2026-09-16.md` - this document

### Risks

- The 12 records that were `verified` and are now `held` have been moved
  backwards in the pipeline. They were "verified but no cadence" and are now
  "held with a generation failure." This is honest state - they cannot
  generate - but it is worse state than before.
- The evidence traceability gate (`check_evidence` in `src/llm.py`) is
  working as designed. It refused copy that the model could not support with
  the record's own research. This is the gate doing its job.
- Relaxing the gate to allow untraceable evidence would let copy through
  that asserts things the record does not support. That is the defect
  `claims.check` exists to catch, and it would catch it at send time instead
  of generation time - more expensive and more embarrassing.

### Recommended Claude action

1. **Do not bulk-approve anything.** There is nothing to approve.
2. **Decide whether the 4 zero-research records are worth researching.**
   Each research call costs credits. The records are verified, so the person
   credits are already spent. The question is whether more research will
   produce usable facts, or whether these domains are too thin to research.
3. **Investigate why persona_angle fails for records with 4 usable research
   rows.** The gate is working correctly, but the model should be able to
   produce traceable evidence from 4 good research rows. The issue may be
   in the prompt (not telling the model to quote specific research) or in
   the traceability check (too strict on phrasing).
4. **The 3 held records need a decision.** Drop them, or refresh their
   research and reset their state. Nothing in the codebase moves records
   out of `held` automatically.
5. **The task's premise was wrong.** The 15 records are not "verified but
   nobody ran generation." They are "verified but generation cannot run
   because the evidence prerequisite is not met." Running generation was
   the right experiment, and the experiment answered the question.
